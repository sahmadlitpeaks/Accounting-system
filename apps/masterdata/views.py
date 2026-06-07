from rest_framework import viewsets

from apps.accounts.permissions import CompanyScopedQuerysetMixin

from .models import Item, Party, TaxCode, UnitOfMeasure, Warehouse
from .serializers import (
    ItemSerializer,
    PartySerializer,
    TaxCodeSerializer,
    UnitOfMeasureSerializer,
    WarehouseSerializer,
)


class PartyViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Party.objects.all()
    serializer_class = PartySerializer
    filterset_fields = ["company", "is_customer", "is_supplier"]


class ItemViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filterset_fields = ["company", "kind"]


class TaxCodeViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = TaxCode.objects.all()
    serializer_class = TaxCodeSerializer
    filterset_fields = ["company", "kind"]


class UnitOfMeasureViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer


class WarehouseViewSet(CompanyScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
