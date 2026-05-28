"use client";
import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";

export type Locale = "en" | "zh";

const ZH: Record<string, string> = {
  // Layout
  "app.title": "Polsia — 智能商业代理",
  "app.desc": "24/7 自动驾驶您的公司运营",
  "brand.subtitle": "AI 商业代理",

  // Sidebar nav
  "nav.dashboard": "仪表盘",
  "nav.agents": "代理",
  "nav.tasks": "任务",
  "nav.social": "社交媒体",
  "nav.outreach": "邮件营销",
  "nav.ads": "广告",
  "nav.finance": "财务",
  "nav.memory": "记忆库",
  "nav.settings": "设置",
  "nav.lang": "English",

  // Dashboard
  "dash.title": "仪表盘",
  "dash.tasks_today": "今日任务",
  "dash.completed": "已完成",
  "dash.failed": "失败",
  "dash.mrr": "月经常收入",
  "dash.active_customers": "活跃客户",
  "dash.churn_rate": "流失率",
  "dash.agent_status": "代理状态",
  "dash.live_activity": "实时动态",

  // Agents page
  "agents.title": "代理",
  "agents.run_now": "立即运行",
  "agents.triggering": "运行中…",
  "agents.last_run": "上次运行",
  "agents.tasks_today": "今日任务数",
  "agents.never": "从未",
  // Agent descriptions
  "agent.orchestrator": "生成每日任务计划和晚间总结",
  "agent.business_planning": "分析策略，更新 KPI，识别机会",
  "agent.competitor_research": "研究竞争对手和市场定位",
  "agent.social_media": "起草和发布推文，监控互动",
  "agent.ads_management": "管理 Google 和 Meta 广告活动",
  "agent.email_outreach": "寻找潜在客户并发送个性化邮件",
  "agent.code_generation": "编写代码，提交到 GitHub，部署上线",
  "agent.customer_support": "读取收件箱并草拟客户回复",
  "agent.finance": "监控 Stripe 收入、支出和告警",

  // Tasks page
  "tasks.title": "任务",
  "tasks.empty": "暂无任务。代理将在运行周期中自动创建任务。",
  "tasks.priority": "优先级",
  "status.completed": "已完成",
  "status.in_progress": "进行中",
  "status.pending": "待处理",
  "status.failed": "失败",

  // Finance page
  "finance.title": "财务",
  "finance.last_snapshot": "上次快照",
  "finance.arr": "年经常收入",
  "finance.active_subscribers": "活跃订阅者",
  "finance.stripe_balance": "Stripe 余额",
  "finance.total_ad_spend": "广告总支出",
  "finance.expenses_month": "本月支出",

  // Settings page
  "settings.title": "设置",
  "settings.saved": "设置已保存成功",
  "settings.save": "保存设置",
  "settings.saving": "保存中…",
  "settings.company_profile": "公司信息",
  "settings.company_name": "公司名称",
  "settings.industry": "行业",
  "settings.product_type": "产品类型",
  "settings.website_url": "网站 URL",
  "settings.mission": "使命",
  "settings.vision": "愿景",
  "settings.description": "描述",
  "settings.target_market": "目标市场",
  "settings.value_prop": "价值主张",
  "settings.scheduler": "调度设置",
  "settings.timezone": "时区",
  "settings.morning_cycle": "早晨周期小时 (UTC)",
  "settings.loading": "加载中…",
  "settings.failed": "加载配置失败",

  // Social page
  "social.title": "社交媒体",
  "social.empty": "暂无社交媒体帖子。Social Media 代理将在运行周期中创建内容。",
  "social.scheduled": "计划中",
  "social.posted": "已发布",
  "social.failed_status": "失败",

  // Outreach page
  "outreach.title": "邮件营销",
  "outreach.empty": "暂无邮件活动。Email Outreach 代理将在运行周期中创建活动。",

  // Ads page
  "ads.title": "广告",
  "ads.empty": "暂无广告活动。Ads Management 代理将在运行周期中创建活动。",

  // Memory page
  "memory.title": "记忆库",
  "memory.empty": "暂无记忆条目。代理将在运行中自动生成记忆。",
  "memory.category": "分类",
  "memory.all": "全部",
  "memory.no_results": "无匹配结果",
  "memory.search": "搜索",
  "memory.searching": "搜索中…",
};

const EN: Record<string, string> = {
  "app.title": "Polsia — AI Business Agent",
  "app.desc": "Autonomous AI platform running your company 24/7",
  "brand.subtitle": "AI Business Agent",
  "nav.dashboard": "Dashboard",
  "nav.agents": "Agents",
  "nav.tasks": "Tasks",
  "nav.social": "Social",
  "nav.outreach": "Outreach",
  "nav.ads": "Ads",
  "nav.finance": "Finance",
  "nav.memory": "Memory",
  "nav.settings": "Settings",
  "nav.lang": "中文",
  "dash.title": "Dashboard",
  "dash.tasks_today": "Tasks Today",
  "dash.completed": "completed",
  "dash.failed": "failed",
  "dash.mrr": "MRR",
  "dash.active_customers": "Active Customers",
  "dash.churn_rate": "Churn Rate",
  "dash.agent_status": "Agent Status",
  "dash.live_activity": "Live Activity",
  "agents.title": "Agents",
  "agents.run_now": "Run Now",
  "agents.triggering": "Triggering…",
  "agents.last_run": "Last run",
  "agents.tasks_today": "tasks today",
  "agents.never": "Never",
  "agent.orchestrator": "Generates daily task plans and evening summaries",
  "agent.business_planning": "Analyzes strategy, updates KPIs, identifies opportunities",
  "agent.competitor_research": "Researches competitors and market positioning",
  "agent.social_media": "Drafts and posts tweets, monitors engagement",
  "agent.ads_management": "Manages Google and Meta ad campaigns",
  "agent.email_outreach": "Finds prospects and sends personalized cold emails",
  "agent.code_generation": "Writes code, commits to GitHub, deploys",
  "agent.customer_support": "Reads inbox and drafts customer replies",
  "agent.finance": "Monitors Stripe revenue, expenses, and alerts",
  "tasks.title": "Tasks",
  "tasks.empty": "No tasks yet. Agents will create tasks during their cycles.",
  "tasks.priority": "Priority",
  "status.completed": "Completed",
  "status.in_progress": "In Progress",
  "status.pending": "Pending",
  "status.failed": "Failed",
  "finance.title": "Finance",
  "finance.last_snapshot": "Last snapshot",
  "finance.arr": "ARR",
  "finance.active_subscribers": "Active Subscribers",
  "finance.stripe_balance": "Stripe Balance",
  "finance.total_ad_spend": "Total Ad Spend",
  "finance.expenses_month": "Expenses (Month)",
  "settings.title": "Settings",
  "settings.saved": "Settings saved successfully",
  "settings.save": "Save Settings",
  "settings.saving": "Saving…",
  "settings.company_profile": "Company Profile",
  "settings.company_name": "Company Name",
  "settings.industry": "Industry",
  "settings.product_type": "Product Type",
  "settings.website_url": "Website URL",
  "settings.mission": "Mission",
  "settings.vision": "Vision",
  "settings.description": "Description",
  "settings.target_market": "Target Market",
  "settings.value_prop": "Value Proposition",
  "settings.scheduler": "Scheduler",
  "settings.timezone": "Timezone",
  "settings.morning_cycle": "Morning Cycle Hour (UTC)",
  "settings.loading": "Loading…",
  "settings.failed": "Failed to load config",
  "social.title": "Social Media",
  "social.empty": "No social posts yet. The Social Media agent will create content during its cycles.",
  "social.scheduled": "Scheduled",
  "social.posted": "Posted",
  "social.failed_status": "Failed",
  "outreach.title": "Email Outreach",
  "outreach.empty": "No email campaigns yet. The Email Outreach agent will create campaigns during its cycles.",
  "ads.title": "Ads",
  "ads.empty": "No ad campaigns yet. The Ads Management agent will create campaigns during its cycles.",
  "memory.title": "Memory",
  "memory.empty": "No memory entries yet. Agents will generate memories during their runs.",
  "memory.category": "Category",
  "memory.all": "All",
  "memory.no_results": "No matching results",
  "memory.search": "Search",
  "memory.searching": "Searching…",
};

const LOCALES: Record<Locale, Record<string, string>> = { en: EN, zh: ZH };

type I18nCtx = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
};

const Ctx = createContext<I18nCtx>({
  locale: "en",
  setLocale: () => {},
  t: (k: string) => k,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("polsia-locale");
      if (saved === "zh" || saved === "en") return saved;
    }
    return "en";
  });
  useEffect(() => localStorage.setItem("polsia-locale", locale), [locale]);
  const t = useCallback(
    (key: string) => LOCALES[locale][key] ?? EN[key] ?? key,
    [locale],
  );
  return (
    <Ctx.Provider value={{ locale, setLocale, t }}>
      {children}
    </Ctx.Provider>
  );
}

export function useI18n() {
  return useContext(Ctx);
}
