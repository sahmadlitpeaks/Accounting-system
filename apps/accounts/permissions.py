"""DRF helpers for company-scoped access."""
from .access import user_company_ids


class CompanyScopedQuerysetMixin:
    """Restrict list/detail querysets to companies the requesting user belongs to.

    Assumes the model has a ``company`` FK (directly or via ``company_id``).
    Superusers see everything; anonymous users see nothing.
    """

    company_field = "company_id"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            return qs
        allowed = user_company_ids(user)
        return qs.filter(**{f"{self.company_field}__in": allowed})
