from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Account, AccountingPeriod, JournalEntry
from .reports import balance_sheet, profit_and_loss
from .serializers import (
    AccountingPeriodSerializer,
    AccountSerializer,
    JournalEntrySerializer,
)
from .services import trial_balance


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    filterset_fields = ["company", "type", "is_group"]

    def get_queryset(self):
        qs = super().get_queryset()
        company = self.request.query_params.get("company")
        return qs.filter(company=company) if company else qs


class AccountingPeriodViewSet(viewsets.ModelViewSet):
    queryset = AccountingPeriod.objects.all()
    serializer_class = AccountingPeriodSerializer


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: entries are created through the posting service, not the API,
    to keep the balancing invariant authoritative."""

    queryset = JournalEntry.objects.prefetch_related("lines").all()
    serializer_class = JournalEntrySerializer

    @action(detail=False, methods=["get"], url_path="trial-balance")
    def trial_balance(self, request):
        company = request.query_params.get("company")
        as_of = request.query_params.get("as_of")
        if not company:
            return Response({"detail": "company query param required"}, status=400)
        return Response(trial_balance(company, as_of))


class ReportViewSet(viewsets.ViewSet):
    """Financial statements: profit & loss and balance sheet."""

    def _company(self, request):
        from apps.core.models import Company

        return Company.objects.get(pk=request.query_params["company"])

    @action(detail=False, methods=["get"], url_path="profit-and-loss")
    def profit_and_loss(self, request):
        if "company" not in request.query_params:
            return Response({"detail": "company query param required"}, status=400)
        return Response(profit_and_loss(
            self._company(request),
            start=request.query_params.get("start"),
            end=request.query_params.get("end"),
        ))

    @action(detail=False, methods=["get"], url_path="balance-sheet")
    def balance_sheet(self, request):
        if "company" not in request.query_params:
            return Response({"detail": "company query param required"}, status=400)
        return Response(balance_sheet(
            self._company(request),
            as_of=request.query_params.get("as_of"),
        ))
