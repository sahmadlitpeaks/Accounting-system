from rest_framework.routers import DefaultRouter

from .views import (
    CustomerInvoiceViewSet,
    PurchaseOrderViewSet,
    ReportViewSet,
    SalesOrderViewSet,
    SupplierBillViewSet,
)

router = DefaultRouter()
router.register("sales-orders", SalesOrderViewSet)
router.register("purchase-orders", PurchaseOrderViewSet)
router.register("customer-invoices", CustomerInvoiceViewSet)
router.register("supplier-bills", SupplierBillViewSet)
router.register("reports", ReportViewSet, basename="orders-reports")

urlpatterns = router.urls
