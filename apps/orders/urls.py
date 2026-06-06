from rest_framework.routers import DefaultRouter

from .views import (
    CustomerInvoiceViewSet,
    PurchaseOrderViewSet,
    SalesOrderViewSet,
    SupplierBillViewSet,
)

router = DefaultRouter()
router.register("sales-orders", SalesOrderViewSet)
router.register("purchase-orders", PurchaseOrderViewSet)
router.register("customer-invoices", CustomerInvoiceViewSet)
router.register("supplier-bills", SupplierBillViewSet)

urlpatterns = router.urls
