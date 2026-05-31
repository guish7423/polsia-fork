# Agent 激活指南

> 将 Polsia Fork 从沙箱模式切换为生产运营的逐步操作手册。

---

## 当前状态

所有 10 个 Agent 当前在 **Mock 模式** 运行 — 返回模拟数据，不调用真实 API。
不需要 API Key，不产生费用，适合开发和演示。

```yaml
环境变量:
  SANDBOX_MODE: "true"     # 防止真实 API 调用
  LLM_API_MOCK: "true"     # LLM 返回 mock 响应
  CLAUDE_CLI_MOCK: "true"  # 遗留兼容
```

---

## Step 1: LLM API Key 配置

所有 Agent 共享同一个 LLM 后端（DeepSeek 兼容 API）。

```bash
# 在 backend/.env 中设置
LLM_API_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-deepseek-api-key-here
LLM_MODEL=deepseek-chat        # 或 deepseek-reasoner (更深度思考)

# 可选: 切换到其他兼容 API
# LLM_API_BASE_URL=https://api.openai.com/v1
# LLM_API_KEY=sk-your-openai-api-key
# LLM_MODEL=gpt-4o-mini
```

**费用预估**:
| 模型 | 输入价格 | 输出价格 | 月估算 (10 agents × 100次/天 × 500 tokens) |
|------|---------|---------|--------------------------------------------|
| DeepSeek Chat | ¥1/1M | ¥2/1M | ~¥9/月 |
| DeepSeek Reasoner | ¥4/1M | ¥16/1M | ~¥60/月 |
| GPT-4o-mini | $0.15/1M | $0.60/1M | ~$1.35/月 |

**建议**: 先用 DeepSeek Chat + SANDBOX_MODE=false 做单 Agent 测试。

---

## Step 2: 逐个 Agent 激活

不要一次性全部激活。按以下顺序逐步启用：

### 批次 1: 核心运营 (先做，风险低)

**Orchestrator Agent** (协调器):
```bash
# 保留 SANDBOX_MODE=true — Agent 仍 mock，但协调器开始分配任务
# 验证任务分配逻辑
```

**Business Planning Agent** (商业计划):
```bash
# 观察输出质量
curl -X POST "http://localhost:8000/api/v1/agents/run" \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "business_planning", "task": "分析当前市场趋势"}'
```

**验证**: 检查返回内容是否为真实分析而非 mock 文本。

### 批次 2: 内容生成 (需 LLM，中等风险)

**Social Media Agent** (社媒):
```bash
SANDBOX_MODE=false  # 允许真实的 LLM API 调用
# 但 SANDBOX_MODE=true 阻止 Twitter/Stripe API 调用 — 安全的中间状态
```

**Code Generation Agent** (代码生成):
```bash
# 生成代码片段 — 纯 LLM 调用，零外部 API 风险
```

### 批次 3: 外部调用 (高风险)

**Email Outreach Agent** (邮件外联):
```bash
# 需要:
# - SMTP 服务器配置
# - 邮件模板就绪
# - 收件人列表录入
```

**Ads Agent** (广告):
```bash
# 需要:
# - Google Ads / Facebook Ads API 凭证
# - 预算上限配置
```

**Deployment Agent** (部署):
```bash
# 需要:
# - Railway / Render API Token
# - 生产环境配置
```

---

## Step 3: 生产切换

将 SQLite → PostgreSQL (Railway/Neon/Supabase):
```bash
# .env 配置
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/polsia
```

将 Celery + Redis 切换为生产 Redis:
```bash
# .env 配置
REDIS_URL=redis://user:pass@host:6379
```

关闭 Mock 模式:
```bash
# .env
SANDBOX_MODE=false
LLM_API_MOCK=false
```

---

## Step 4: 监控与成本

### 仪表盘监控
- `/api/v1/dashboard/summary` — 整体运营指标
- `/api/v1/finance/summary` — 费用/收入追踪
- `/api/v1/agents/status` — Agent 实时状态

### 成本控制
```python
# app/core/settings.py 中已内置:
LLM_COST_LIMIT_DAILY = 2.0     # 每日 LLM 费用上限 (USD)
LLM_COST_LIMIT_MONTHLY = 50.0  # 每月上限
```

### 日志
```bash
# Agent 运行日志
tail -f backend/logs/agents.log

# LLM API 调用日志 (含 token 计数)
tail -f backend/logs/llm_calls.log
```

---

## 回滚方案

任何时候遇到问题，回退到安全状态:

```bash
# 立即停止所有真实调用
export SANDBOX_MODE=true
export LLM_API_MOCK=true

# 重启服务
uvicorn app.main:app --port 8000

# 确认所有 Agent 返回 mock 响应
curl http://localhost:8000/api/v1/agents/status
# 检查: 所有 agent status 应为 "idle" 且无真实 API 调用
```

---

## 激活顺序总结

```
Phase 1 (立即):
  └─ 配置 LLM API Key → 单 Agent 测试验证
  
Phase 2 (低风险):
  ├─ Orchestrator + Business Planning (无外部 API)
  ├─ Code Generation (纯 LLM)
  └─ Social Media → LLM only, SANDBOX_MODE true

Phase 3 (中风险):
  ├─ Competitor Research (web search)
  ├─ Customer Support → 需先配知识库
  └─ Finance → 仅追踪，不执行交易

Phase 4 (高风险 - 需手工确认):
  ├─ Email Outreach → 收件人列表 + 模板就绪后
  ├─ Ads → 预算上限确认后
  └─ Deployment → 生产环境就绪后
```

> ⚠️ **Golden Rule**: 每个 Phase 之间的间隔 ≥ 24 小时，确认无异常后再推进。
> ⚠️ **Golden Rule**: 永远不要在一个 Agent 上同时设置 SANDBOX_MODE=false + 真实外部凭证。
