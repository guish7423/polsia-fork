from dataclasses import dataclass

@dataclass
class PlanTier:
    name: str
    label: str
    price_monthly_cents: int
    price_yearly_cents: int
    stripe_price_id_monthly: str  # Set from env
    stripe_price_id_yearly: str
    agents_limit: int
    tasks_monthly_limit: int
    memory_limit_mb: int
    custom_domain: bool
    priority_support: bool


# Default price IDs — override via environment variables
PLANS: dict[str, PlanTier] = {
    "free": PlanTier(
        name="free",
        label="Free",
        price_monthly_cents=0,
        price_yearly_cents=0,
        stripe_price_id_monthly="",
        stripe_price_id_yearly="",
        agents_limit=3,
        tasks_monthly_limit=100,
        memory_limit_mb=50,
        custom_domain=False,
        priority_support=False,
    ),
    "starter": PlanTier(
        name="starter",
        label="Starter",
        price_monthly_cents=1999,  # $19.99/mo
        price_yearly_cents=19990,  # $199.90/yr (~$16.66/mo)
        stripe_price_id_monthly="",
        stripe_price_id_yearly="",
        agents_limit=10,
        tasks_monthly_limit=5000,
        memory_limit_mb=500,
        custom_domain=False,
        priority_support=False,
    ),
    "pro": PlanTier(
        name="pro",
        label="Pro",
        price_monthly_cents=9999,  # $99.99/mo
        price_yearly_cents=99990,  # $999.90/yr (~$83.33/mo)
        stripe_price_id_monthly="",
        stripe_price_id_yearly="",
        agents_limit=50,
        tasks_monthly_limit=50000,
        memory_limit_mb=2000,
        custom_domain=True,
        priority_support=True,
    ),
}


def get_plan(plan_name: str) -> PlanTier | None:
    """Get plan by name. Case-insensitive."""
    return PLANS.get(plan_name.lower())


def get_plan_from_price_id(price_id: str) -> PlanTier | None:
    """Find plan that matches a Stripe price ID."""
    for plan in PLANS.values():
        if plan.stripe_price_id_monthly == price_id or plan.stripe_price_id_yearly == price_id:
            return plan
    return None


def list_plans() -> list[dict]:
    """Return all plans as serializable dicts."""
    return [
        {
            "name": p.name,
            "label": p.label,
            "price_monthly_cents": p.price_monthly_cents,
            "price_yearly_cents": p.price_yearly_cents,
            "agents_limit": p.agents_limit,
            "tasks_monthly_limit": p.tasks_monthly_limit,
            "memory_limit_mb": p.memory_limit_mb,
            "custom_domain": p.custom_domain,
            "priority_support": p.priority_support,
        }
        for p in PLANS.values()
    ]
