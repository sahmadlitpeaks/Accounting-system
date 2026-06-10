from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import BillOfMaterial, BOMLine, WorkOrder
from .services import ManufacturingError, complete_work_order


class BOMLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BOMLine
        fields = ["id", "component", "quantity"]


class BillOfMaterialSerializer(serializers.ModelSerializer):
    lines = BOMLineSerializer(many=True)

    class Meta:
        model = BillOfMaterial
        fields = ["id", "company", "product", "name", "is_active", "lines"]

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        bom = BillOfMaterial.objects.create(**validated_data)
        for line in lines:
            BOMLine.objects.create(bom=bom, **line)
        return bom


class WorkOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrder
        fields = "__all__"
        read_only_fields = ["status", "produced_cost"]


class BillOfMaterialViewSet(viewsets.ModelViewSet):
    queryset = BillOfMaterial.objects.prefetch_related("lines").all()
    serializer_class = BillOfMaterialSerializer
    filterset_fields = ["company"]


class WorkOrderViewSet(viewsets.ModelViewSet):
    queryset = WorkOrder.objects.select_related("bom__product").all()
    serializer_class = WorkOrderSerializer
    filterset_fields = ["company", "status"]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        try:
            wo = complete_work_order(self.get_object())
        except ManufacturingError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(WorkOrderSerializer(wo).data)
