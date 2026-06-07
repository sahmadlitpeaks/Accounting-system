"""Posted-entry immutability guard.

Once a journal entry is POSTED it (and its lines) must never be edited or
deleted — corrections are made with reversing entries / credit notes. The
posting service creates entries already-posted and bulk-creates lines (which
bypasses pre_save), so these guards only ever fire on illegitimate edits via the
ORM, admin, or shell.
"""
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import JournalEntry, JournalLine


class ImmutablePostingError(ValidationError):
    pass


@receiver(pre_save, sender=JournalEntry)
def _guard_entry_update(sender, instance, **kwargs):
    if not instance.pk:
        return  # new entry
    old_status = (
        JournalEntry.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )
    if old_status == JournalEntry.Status.POSTED:
        raise ImmutablePostingError(
            f"Journal entry {instance.pk} is posted and cannot be modified. "
            "Reverse it instead."
        )


@receiver(pre_delete, sender=JournalEntry)
def _guard_entry_delete(sender, instance, **kwargs):
    if instance.status == JournalEntry.Status.POSTED:
        raise ImmutablePostingError(f"Posted journal entry {instance.pk} cannot be deleted.")


@receiver(pre_save, sender=JournalLine)
def _guard_line_update(sender, instance, **kwargs):
    if instance.pk and instance.entry.status == JournalEntry.Status.POSTED:
        raise ImmutablePostingError("Lines of a posted journal entry cannot be modified.")


@receiver(pre_delete, sender=JournalLine)
def _guard_line_delete(sender, instance, **kwargs):
    if instance.entry.status == JournalEntry.Status.POSTED:
        raise ImmutablePostingError("Lines of a posted journal entry cannot be deleted.")
