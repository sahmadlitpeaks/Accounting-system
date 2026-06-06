from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from apps.masterdata.models import Item

from .models import StockMove
from .services import stock_on_hand, stock_value


class StockMoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMove
        fields = "__all__"


class StockMoveViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMove.objects.all()
    serializer_class = StockMoveSerializer
    filterset_fields = ["company", "item", "warehouse"]

    @action(detail=False, methods=["get"], url_path="on-hand")
    def on_hand(self, request):
        item_id = request.query_params.get("item")
        if not item_id:
            return Response({"detail": "item query param required"}, status=400)
        item = Item.objects.get(pk=item_id)
        return Response(
            {
                "item": item.sku,
                "quantity_on_hand": stock_on_hand(item),
                "stock_value": stock_value(item),
            }
        )
