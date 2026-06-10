from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AssetCategory, FixedAsset
from .services import AssetError, dispose_asset, run_depreciation


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = "__all__"


class FixedAssetSerializer(serializers.ModelSerializer):
    book_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    monthly_depreciation = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = FixedAsset
        fields = "__all__"


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    filterset_fields = ["company"]


class FixedAssetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FixedAsset.objects.select_related("category").all()
    serializer_class = FixedAssetSerializer
    filterset_fields = ["company", "status"]

    @action(detail=False, methods=["post"], url_path="run-depreciation")
    def run_depreciation(self, request):
        from datetime import date as _date

        from apps.core.models import Company

        company = Company.objects.get(pk=request.data["company"])
        period_date = request.data.get("date") or _date.today()
        entries = run_depreciation(company, period_date)
        return Response({"depreciated_assets": len(entries)}, status=201)

    @action(detail=True, methods=["post"])
    def dispose(self, request, pk=None):
        from datetime import date as _date

        try:
            entry = dispose_asset(
                self.get_object(),
                request.data.get("date") or _date.today(),
                proceeds=request.data.get("proceeds", 0),
            )
        except AssetError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"journal_entry": entry.id}, status=201)
