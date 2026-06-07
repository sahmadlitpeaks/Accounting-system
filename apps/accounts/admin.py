from django.contrib import admin

from .models import AuditLog, Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role")
    list_filter = ("role", "company")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model", "object_id", "company")
    list_filter = ("action", "model", "company")
    search_fields = ("object_id", "object_repr")
    readonly_fields = ("timestamp", "user", "action", "app_label", "model", "object_id", "object_repr", "company", "changes")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # audit log is append-only
