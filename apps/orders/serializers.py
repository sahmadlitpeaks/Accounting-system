from rest_framework import serializers

from .models import (
    CustomerInvoice,
    PurchaseOrder,
    SalesOrder,
    SalesOrderLine,
    SupplierBill,
)


class SalesOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesOrderLine
        fields = ["id", "item", "quantity", "unit_price", "tax_code"]


class SalesOrderSerializer(serializers.ModelSerializer):
    lines = SalesOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = SalesOrder
        fields = "__all__"


class SalesOrderWriteSerializer(serializers.ModelSerializer):
    """Create a sales order with nested lines in one request."""

    lines = SalesOrderLineSerializer(many=True)

    class Meta:
        model = SalesOrder
        fields = ["id", "company", "party", "date", "currency", "fx_rate",
                  "warehouse", "reference", "lines"]

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        order = SalesOrder.objects.create(**validated_data)
        for line in lines:
            SalesOrderLine.objects.create(order=order, **line)
        return order


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
