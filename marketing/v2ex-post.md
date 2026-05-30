# V2EX 发帖 — Polsia Fork 国内版

## 标题
一人公司神器：Fork 了 Polsia（$1000万ARR），开源全栈 AI 自动运营系统，微信收款

## 正文

先说说背景。我是一个人的开发者，去年开始研究 Polsia——这家公司估值 $2.5 亿、单人运营、ARR 接近 $1000 万，号称「AI 自动运行公司」。

研究完我发现：**他们的核心代码根本不在开源仓库里**。前端是完整的，但后端（Agent 实现、FastAPI 应用、数据模型、API 路由）全部缺失，只是一个空壳。

于是我从零重写了整个后端（Python），保留前端，做成了一套国内可直接跑的版本。

### 10 个 AI Agent 能做什么

| Agent | 干什么 |
|-------|--------|
| 👑 CEO/Orchestrator | 规划每日任务、分派工作、生成日报 |
| 📊 商业分析 | 市场研究、商业模式设计、增长策略 |
| 🔍 竞品监控 | 自动追踪对手动态、价格变化、产品更新 |
| 📱 社媒运营 | 内容创作、定时发布、多平台管理 |
| ✉️ 邮件营销 | 客户开发、邮件自动化、跟进流程 |
| 📢 广告管理 | 投放优化、预算追踪、A/B 测试 |
| 💬 客服 | 工单分类、自动回复、知识库维护 |
| 💻 代码生成 | 自动编程、Bug 修复、功能实现 |
| 💰 财务 | 收入/支出追踪、报表生成、成本监控 |
| 🚀 部署 | 基础设施管理、CI/CD 流水线 |

每天早上 Orchestrator 制定计划 → Agent 并行执行 → 晚上汇总报告。

### 和原版 Polsia 的区别

| 维度 | 原版 Polsia | Polsia Fork |
|------|-------------|-------------|
| 后端核心 | 闭源 | ✅ 开源重写 |
| LLM 调用 | Claude Code CLI（需安装 Claude） | ✅ 标准 LLM API（兼容 DeepSeek/OpenAI） |
| 成本 | 按 Claude 调用付费 | ✅ 自带 Token 成本追踪仪表盘 |
| 语言 | 英文 | ✅ 中英双语 |
| 部署 | 仅支持 Render | ✅ Docker 一键部署 |

### 技术栈

- **后端**: Python 3.12 + FastAPI async + SQLAlchemy + Celery + Redis
- **前端**: Next.js 14（中英文双语，13 个页面）
- **数据库**: PostgreSQL（兼容 SQLite 开发）
- **LLM**: DeepSeek API（兼容 OpenAI 格式），自带成本追踪
- **测试**: 74 个测试全部通过，CI 就绪
- **部署**: Docker + docker-compose + GitHub Actions

### 快速体验

```bash
git clone https://github.com/guish7423/polsia-fork.git
cd polsia-fork
cp .env.example .env  # 设置 LLM_API_KEY
docker compose up -d
# 访问 http://localhost:3000
```

5 分钟启动你的 AI 公司运营平台。

### 项目地址

**GitHub**: https://github.com/guish7423/polsia-fork

### 求建议

我做这个项目的初衷是：一个人也能运营一家公司。目前的想法是两条腿走路：

1. **服务先行**：帮小企业/个体户部署这套系统，¥2K-5K/单 + 月维护费
2. **产品化 SaaS**：做标准化产品，¥99-199/月

想听听大家的意见：
- 这种 AI 运营公司的产品在国内有市场吗？
- 定价多少合适？
- 推荐在哪些渠道推广？（V2EX/电鸭/小红书/知乎？）

欢迎 Star ⭐ 和提 Issue！

### 联系方式
- 微信/支付宝收款
- 提供部署文档 + 远程协助
- 功能定制也接

**有兴趣请留言或私信，附上需求即可。**
