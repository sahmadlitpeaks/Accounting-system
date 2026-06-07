from rest_framework import serializers

from .models import AuditLog, Membership


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "user", "company", "role"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "timestamp", "user", "action", "app_label", "model",
                  "object_id", "object_repr", "company", "changes"]
