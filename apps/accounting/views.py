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
    filterset_fields = ["company", "status"]

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        from .closing import close_period
        from .services import PostingError

        try:
            close_period(self.get_object())
        except PostingError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"status": "closed"})

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        from .closing import reopen_period

        reopen_period(self.get_object())
        return Response({"status": "open"})

    @action(detail=False, methods=["post"], url_path="close-year")
    def close_year(self, request):
        from apps.core.models import Company

        from .closing import close_year
        from .serializers import JournalEntrySerializer

        data = request.data
        company = Company.objects.get(pk=data["company"])
        entry = close_year(company, data["start"], data["end"])
        if entry is None:
            return Response({"detail": "nothing to close"})
        return Response(JournalEntrySerializer(entry).data, status=201)


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
