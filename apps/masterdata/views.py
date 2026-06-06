from rest_framework import viewsets

from .models import Item, Party, TaxCode, UnitOfMeasure, Warehouse
from .serializers import (
    ItemSerializer,
    PartySerializer,
    TaxCodeSerializer,
    UnitOfMeasureSerializer,
    WarehouseSerializer,
)


class PartyViewSet(viewsets.ModelViewSet):
    queryset = Party.objects.all()
    serializer_class = PartySerializer
    filterset_fields = ["company", "is_customer", "is_supplier"]


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filterset_fields = ["company", "kind"]


class TaxCodeViewSet(viewsets.ModelViewSet):
    queryset = TaxCode.objects.all()
    serializer_class = TaxCodeSerializer
    filterset_fields = ["company", "kind"]


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
