"""Append-only audit logging via model signals.

Records create/update/delete on a curated set of financially-significant models,
attributing each change to the current request user when available.
"""
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .middleware import get_current_user
from .models import AuditLog

# "app_label.ModelName" of models to audit.
AUDITED = {
    "accounting.JournalEntry",
    "orders.CustomerInvoice",
    "orders.CustomerCreditNote",
    "orders.SupplierBill",
    "orders.Payment",
    "masterdata.Party",
    "masterdata.Item",
    "accounts.Membership",
}


def _label(instance):
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"


def _company_of(instance):
    company = getattr(instance, "company", None)
    return company if company is not None and company.__class__.__name__ == "Company" else None


@receiver(pre_save)
def _capture_dirty(sender, instance, **kwargs):
    label = f"{sender._meta.app_label}.{sender.__name__}"
    if label not in AUDITED or not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    changes = {}
    for field in sender._meta.fields:
        name = field.attname
        before = getattr(old, name)
        after = getattr(instance, name)
        if before != after:
            changes[name] = [str(before), str(after)]
    instance._audit_changes = changes


@receiver(post_save)
def _log_save(sender, instance, created, **kwargs):
    label = f"{sender._meta.app_label}.{sender.__name__}"
    if label not in AUDITED:
        return
    AuditLog.objects.create(
        user=_user(),
        action="create" if created else "update",
        app_label=sender._meta.app_label,
        model=sender.__name__,
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        company=_company_of(instance),
        changes={} if created else getattr(instance, "_audit_changes", {}),
    )


@receiver(post_delete)
def _log_delete(sender, instance, **kwargs):
    label = f"{sender._meta.app_label}.{sender.__name__}"
    if label not in AUDITED:
        return
    AuditLog.objects.create(
        user=_user(),
        action="delete",
        app_label=sender._meta.app_label,
        model=sender.__name__,
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        company=_company_of(instance),
    )


def _user():
    user = get_current_user()
    return user if (user is not None and getattr(user, "is_authenticated", False)) else None
