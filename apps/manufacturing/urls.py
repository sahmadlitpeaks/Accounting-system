from rest_framework.routers import DefaultRouter

from .views import BillOfMaterialViewSet, WorkOrderViewSet

router = DefaultRouter()
router.register("boms", BillOfMaterialViewSet)
router.register("work-orders", WorkOrderViewSet)

urlpatterns = router.urls
