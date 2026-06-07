from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CustomerInvoice, PurchaseOrder, SalesOrder, SupplierBill
from .serializers import (
    CustomerInvoiceSerializer,
    PurchaseOrderSerializer,
    SalesOrderSerializer,
    SupplierBillSerializer,
)
from .services import (
    OrderError,
    bill_purchase_order,
    deliver_sales_order,
    invoice_sales_order,
    receive_purchase_order,
)


class SalesOrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SalesOrder.objects.prefetch_related("lines").all()
    serializer_class = SalesOrderSerializer
    filterset_fields = ["company", "status"]

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        try:
            deliver_sales_order(self.get_object())
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"status": "delivered"})

    @action(detail=True, methods=["post"])
    def invoice(self, request, pk=None):
        number = request.data.get("number", "")
        try:
            invoice = invoice_sales_order(self.get_object(), number=number)
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(CustomerInvoiceSerializer(invoice).data, status=201)


class PurchaseOrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PurchaseOrder.objects.prefetch_related("lines").all()
    serializer_class = PurchaseOrderSerializer
    filterset_fields = ["company", "status"]

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        try:
            receive_purchase_order(self.get_object())
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"status": "received"})

    @action(detail=True, methods=["post"])
    def bill(self, request, pk=None):
        number = request.data.get("number", "")
        bill = bill_purchase_order(self.get_object(), number=number)
        return Response(SupplierBillSerializer(bill).data, status=201)


class ReportViewSet(viewsets.ViewSet):
    """Receivables / payables aging."""

    def _company(self, request):
        from apps.core.models import Company

        return Company.objects.get(pk=request.query_params["company"])

    @action(detail=False, methods=["get"], url_path="ar-aging")
    def ar_aging(self, request):
        from .reports import ar_aging

        if "company" not in request.query_params:
            return Response({"detail": "company query param required"}, status=400)
        return Response(ar_aging(self._company(request), request.query_params.get("as_of")))

    @action(detail=False, methods=["get"], url_path="ap-aging")
    def ap_aging(self, request):
        from .reports import ap_aging

        if "company" not in request.query_params:
            return Response({"detail": "company query param required"}, status=400)
        return Response(ap_aging(self._company(request), request.query_params.get("as_of")))


class CustomerInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomerInvoice.objects.prefetch_related("lines").all()
    serializer_class = CustomerInvoiceSerializer
    filterset_fields = ["company", "status", "fiscal_status"]


class SupplierBillViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SupplierBill.objects.prefetch_related("lines").all()
    serializer_class = SupplierBillSerializer
    filterset_fields = ["company", "status"]
