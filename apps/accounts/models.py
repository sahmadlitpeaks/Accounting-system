"""Access control and audit.

* ``Membership`` ties a user to a company with a role (multi-company: a user can
  belong to several companies with different roles). Roles map to capabilities.
* ``AuditLog`` is an append-only who/what/when record of changes to key models.
"""
from django.conf import settings
from django.db import models

from apps.core.models import Company, TimeStampedModel


class Role(models.TextChoices):
    ADMIN = "admin", "Administrator"
    ACCOUNTANT = "accountant", "Accountant"
    AP_CLERK = "ap_clerk", "Accounts Payable Clerk"
    AR_CLERK = "ar_clerk", "Accounts Receivable Clerk"
    AUDITOR = "auditor", "Auditor (read-only)"


# Capability -> roles allowed. Used by permission checks.
CAPABILITIES = {
    "manage_users": {Role.ADMIN},
    "post_journal": {Role.ADMIN, Role.ACCOUNTANT},
    "close_period": {Role.ADMIN, Role.ACCOUNTANT},
    "manage_sales": {Role.ADMIN, Role.ACCOUNTANT, Role.AR_CLERK},
    "manage_purchases": {Role.ADMIN, Role.ACCOUNTANT, Role.AP_CLERK},
    "approve_payment": {Role.ADMIN, Role.ACCOUNTANT},
    "create_payment": {Role.ADMIN, Role.ACCOUNTANT, Role.AP_CLERK, Role.AR_CLERK},
    "view": {Role.ADMIN, Role.ACCOUNTANT, Role.AP_CLERK, Role.AR_CLERK, Role.AUDITOR},
}


class Membership(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices)

    class Meta:
        unique_together = ("user", "company")

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.role})"


class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=8)  # create / update / delete
    app_label = models.CharField(max_length=40)
    model = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255, blank=True)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} {self.model}#{self.object_id}"
