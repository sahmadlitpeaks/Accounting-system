from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import BankAccount, BankStatement, BankStatementLine
from .services import auto_match, import_statement_csv, match_manually


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = "__all__"


class BankStatementLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankStatementLine
        fields = "__all__"


class BankStatementSerializer(serializers.ModelSerializer):
    lines = BankStatementLineSerializer(many=True, read_only=True)

    class Meta:
        model = BankStatement
        fields = "__all__"


class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    filterset_fields = ["company"]

    @action(detail=True, methods=["post"], url_path="import-statement")
    def import_statement(self, request, pk=None):
        """Body: {statement_date, reference?, csv} with rows date,description,amount."""
        account = self.get_object()
        statement = import_statement_csv(
            account, request.data["csv"], request.data["statement_date"],
            reference=request.data.get("reference", ""),
        )
        result = auto_match(statement)
        return Response({"statement": statement.id, **result}, status=201)


class BankStatementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BankStatement.objects.prefetch_related("lines").all()
    serializer_class = BankStatementSerializer

    @action(detail=True, methods=["post"], url_path="auto-match")
    def rematch(self, request, pk=None):
        return Response(auto_match(self.get_object()))

    @action(detail=True, methods=["post"], url_path="match-line")
    def match_line(self, request, pk=None):
        """Body: {line, payment} — manual match for leftovers."""
        from apps.orders.models import Payment

        line = BankStatementLine.objects.get(pk=request.data["line"], statement=self.get_object())
        payment = Payment.objects.get(pk=request.data["payment"])
        match_manually(line, payment)
        return Response({"status": "matched"})
