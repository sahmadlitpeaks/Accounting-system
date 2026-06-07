"""Role/capability checks and company-scoped data access."""
from .models import CAPABILITIES, Membership


def user_company_ids(user):
    """Companies the user may access (empty for anonymous; all for superuser)."""
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        from apps.core.models import Company

        return list(Company.objects.values_list("id", flat=True))
    return list(Membership.objects.filter(user=user).values_list("company_id", flat=True))


def role_in(user, company) -> str | None:
    if user and user.is_superuser:
        from .models import Role

        return Role.ADMIN
    m = Membership.objects.filter(user=user, company=company).first()
    return m.role if m else None


def can(user, company, capability: str) -> bool:
    """True if the user's role in ``company`` grants ``capability``."""
    if user and user.is_superuser:
        return True
    role = role_in(user, company)
    return role is not None and role in {r.value for r in CAPABILITIES.get(capability, set())}


class PermissionDenied(Exception):
    pass


def require(user, company, capability: str):
    if not can(user, company, capability):
        raise PermissionDenied(f"User lacks capability '{capability}' for company {getattr(company, 'id', company)}.")
