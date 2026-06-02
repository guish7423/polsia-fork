"""Test the state machine — transition validation + all statuses."""

import pytest

from app.core.status_machine import (
    TaskStatus,
    transition_status,
    OrderStatus,
    transition_order_status,
    PaymentStatus,
)


class TestTaskStatus:
    def test_valid_transitions(self):
        """合法的状态转换路径"""
        s = TaskStatus.PENDING
        s = transition_status(s, TaskStatus.IN_PROGRESS)  # ✅
        s = transition_status(s, TaskStatus.COMPLETED)  # ✅
        assert s == TaskStatus.COMPLETED

    def test_blocked_cycle(self):
        """BLOCKED → IN_PROGRESS → BLOCKED"""
        s = TaskStatus.IN_PROGRESS
        s = transition_status(s, TaskStatus.BLOCKED)
        assert s == TaskStatus.BLOCKED
        s = transition_status(s, TaskStatus.IN_PROGRESS)
        assert s == TaskStatus.IN_PROGRESS

    def test_paused_resume(self):
        """PAUSED → IN_PROGRESS"""
        s = TaskStatus.IN_PROGRESS
        s = transition_status(s, TaskStatus.PAUSED)
        assert s == TaskStatus.PAUSED
        s = transition_status(s, TaskStatus.IN_PROGRESS)
        assert s == TaskStatus.IN_PROGRESS

    def test_review_then_complete(self):
        """IN_PROGRESS → REVIEW → COMPLETED"""
        s = TaskStatus.IN_PROGRESS
        s = transition_status(s, TaskStatus.REVIEW)
        assert s == TaskStatus.REVIEW
        s = transition_status(s, TaskStatus.COMPLETED)
        assert s == TaskStatus.COMPLETED

    def test_illegal_transition(self):
        """非法转换应抛 ValueError"""
        with pytest.raises(ValueError, match="Illegal transition"):
            transition_status(TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS)

        with pytest.raises(ValueError, match="Illegal transition"):
            transition_status(TaskStatus.PENDING, TaskStatus.COMPLETED)

    def test_idempotent_transition(self):
        """同状态转换应允许 (PENDING → PENDING)"""
        s = transition_status(TaskStatus.PENDING, TaskStatus.PENDING)
        assert s == TaskStatus.PENDING

    def test_all_terminal_states(self):
        """终态不可转出"""
        for terminal in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            for dest in TaskStatus:
                if dest == terminal:
                    continue
                with pytest.raises(ValueError):
                    transition_status(terminal, dest)

    def test_enum_value_alias(self):
        """枚举 value 与 DB 字符串兼容"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.PAUSED.value == "paused"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"


class TestOrderStatus:
    def test_scanned_to_completed(self):
        """合法订单路径: scanned → evaluated → accepted → in_progress → completed"""
        s = OrderStatus.SCANNED
        s = transition_order_status(s, OrderStatus.EVALUATED)
        s = transition_order_status(s, OrderStatus.ACCEPTED)
        s = transition_order_status(s, OrderStatus.IN_PROGRESS)
        s = transition_order_status(s, OrderStatus.COMPLETED)
        assert s == OrderStatus.COMPLETED

    def test_rejection(self):
        """SCANNED → REJECTED (终态)"""
        s = transition_order_status(OrderStatus.SCANNED, OrderStatus.REJECTED)
        assert s == OrderStatus.REJECTED
        with pytest.raises(ValueError):
            transition_order_status(OrderStatus.REJECTED, OrderStatus.ACCEPTED)


class TestPaymentStatus:
    def test_values(self):
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.COMPLETED.value == "completed"

    def test_full_lifecycle(self):
        """PaymentStatus 目前无状态机约束"""
        assert PaymentStatus.REFUNDED.value == "refunded"
