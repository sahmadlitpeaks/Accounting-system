from rest_framework import serializers

from .models import Account, AccountingPeriod, JournalEntry, JournalLine


class AccountSerializer(serializers.ModelSerializer):
    normal_balance = serializers.CharField(read_only=True)

    class Meta:
        model = Account
        fields = [
            "id", "company", "code", "name", "type", "subtype",
            "parent", "is_group", "is_active", "normal_balance",
        ]


class JournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = [
            "id", "account", "description", "currency", "fx_rate",
            "debit", "credit", "base_debit", "base_credit", "party",
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id", "company", "date", "period", "reference", "memo",
            "source_type", "source_id", "status", "reversal_of", "lines",
        ]


class AccountingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingPeriod
        fields = "__all__"
