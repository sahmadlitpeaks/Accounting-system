from rest_framework import serializers

from .models import CustomerInvoice, PurchaseOrder, SalesOrder, SupplierBill


class SalesOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesOrder
        fields = "__all__"


class PurchaseOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = "__all__"


class CustomerInvoiceSerializer(serializers.ModelSerializer):
    amount_due = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = CustomerInvoice
        fields = "__all__"


class SupplierBillSerializer(serializers.ModelSerializer):
    amount_due = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = SupplierBill
        fields = "__all__"
