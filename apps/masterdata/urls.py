from rest_framework.routers import DefaultRouter

from .views import (
    ItemViewSet,
    PartyViewSet,
    TaxCodeViewSet,
    UnitOfMeasureViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register("parties", PartyViewSet)
router.register("items", ItemViewSet)
router.register("tax-codes", TaxCodeViewSet)
router.register("uoms", UnitOfMeasureViewSet)
router.register("warehouses", WarehouseViewSet)

urlpatterns = router.urls
