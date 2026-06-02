"""状态机构约 — 确保所有任务状态变更合法 + 可追溯。

核心概念（借鉴 LangGraph Reducer 模式）：
  - 每个状态字段有一张明确的「当前→允许的下一个」转换表
  - 非法转换抛 ValueError（早崩溃比静默吞掉好）
  - 新增 BLOCKED/PAUSED 状态为未来 HITL（Human-in-the-Loop）铺路

用法：
    from app.core.status_machine import TaskStatus, TaskStatusField

    class MyModel(Base):
        status: TaskStatusField = Column(String, default=TaskStatusField.PENDING)
        # 赋值自动验证:
        # obj.status = TaskStatus.IN_PROGRESS  # ✅
        # obj.status = "completed"             # ✅ (str 自动转)
        # obj.status = "bogus"                 # ❌ ValueError
"""

from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    """任务状态枚举。全大写常量名，小写 value 保持 DB 兼容。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # Phase 0 新增 — 为 HITL 准备
    BLOCKED = "blocked"  # 等待外部审批/输入
    PAUSED = "paused"  # 被人类或系统暂停

    REVIEW = "in_review"  # 等待审查

    def __str__(self) -> str:
        return self.value


# ─── 状态转换表 ──────────────────────────────────────
# 每个当前状态 → 允许的下一个状态集合

_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.BLOCKED}
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.PAUSED,
            TaskStatus.REVIEW,
        }
    ),
    TaskStatus.BLOCKED: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.PAUSED}
    ),
    TaskStatus.PAUSED: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.COMPLETED}
    ),
    TaskStatus.REVIEW: frozenset(
        {TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.BLOCKED}
    ),
    TaskStatus.COMPLETED: frozenset(),  # 终态 — 不可转出
    TaskStatus.FAILED: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}
    ),  # 允许重试
    TaskStatus.CANCELLED: frozenset(),  # 终态
}


def transition_status(current: TaskStatus, new: TaskStatus) -> TaskStatus:
    """原子化状态转换。

    允许：
      - 从当前状态 → 同状态 (idempotent)
      - 从当前状态 → 转换表允许的下一个状态

    Raises:
        ValueError: 如果转换非法。
    """
    if current == new:
        return new  # idempotent — 同状态不验证
    allowed = _TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        allowed_str = ", ".join(s.value for s in sorted(allowed, key=lambda x: x.value))
        raise ValueError(
            f"Illegal transition: '{current.value}' → '{new.value}'. "
            f"From '{current.value}' you can go to: [{allowed_str}]"
        )
    return new


# ─── SQLAlchemy Descriptor ──────────────────────────


class TaskStatusField:
    """SQLAlchemy 模型字段描述器，自动 toString + 转换验证。

    在模型中使用:
        class Task(Base):
            status: TaskStatusField = Column(String, default=TaskStatus.PENDING)

    行为:
        - 赋值 TaskStatus 枚举 → 自动转 value(string) 写入 DB
        - 赋值 str → 自动转 TaskStatus 再验证合法性
        - 赋值非法值 → ValueError
        - 读取 → 返回 TaskStatus 枚举（非 str）
        - 初始值为 PENDING
    """

    PENDING = "pending"

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name
        self._private = f"_{name}"

    def __get__(self, obj: Any, objtype: Optional[type] = None) -> TaskStatus:
        """读取时返回 TaskStatus 枚举。"""
        if obj is None:
            return TaskStatus.PENDING  # 类级访问（用于 Column default）
        raw = obj.__dict__.get(self._private, TaskStatus.PENDING)
        if isinstance(raw, TaskStatus):
            return raw
        return TaskStatus(raw) if raw else TaskStatus.PENDING

    def __set__(self, obj: Any, value: Any) -> None:
        """赋值时自动验证。

        支持:
          - TaskStatus 枚举: 直接验证
          - str: 自动转型验证
          - None: 设回 PENDING
        """
        if value is None:
            resolved = TaskStatus.PENDING
        elif isinstance(value, TaskStatus):
            resolved = value
        elif isinstance(value, str):
            resolved = TaskStatus(value)
        else:
            raise TypeError(f"Expected str, TaskStatus, or None, got {type(value).__name__}")

        # 如果不是首次赋值，校验转换合法性
        current_raw = obj.__dict__.get(self._private)
        if current_raw is not None:
            current = TaskStatus(current_raw) if isinstance(current_raw, str) else current_raw
            if current != resolved:
                resolved = transition_status(current, resolved)

        obj.__dict__[self._private] = resolved


# ─── ExternalOrder 专用状态 ─────────────────────────


class OrderStatus(str, Enum):
    """外部订单状态。有独立的状态机。"""

    SCANNED = "scanned"
    EVALUATED = "evaluated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


_ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.SCANNED: frozenset({OrderStatus.EVALUATED, OrderStatus.REJECTED}),
    OrderStatus.EVALUATED: frozenset({OrderStatus.ACCEPTED, OrderStatus.REJECTED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED}),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.IN_PROGRESS: frozenset({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


def transition_order_status(current: OrderStatus, new: OrderStatus) -> OrderStatus:
    """原子化外部订单状态转换。"""
    allowed = _ORDER_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        allowed_str = ", ".join(s.value for s in sorted(allowed, key=lambda x: x.value))
        raise ValueError(
            f"Illegal order transition: '{current.value}' → '{new.value}'. "
            f"Allowed: [{allowed_str}]"
        )
    return new


# ─── 支付状态 ──────────────────────────────────────


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

    def __str__(self) -> str:
        return self.value
