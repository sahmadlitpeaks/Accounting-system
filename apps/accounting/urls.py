from rest_framework.routers import DefaultRouter

from .views import (
    AccountingPeriodViewSet,
    AccountViewSet,
    JournalEntryViewSet,
    ReportViewSet,
)

router = DefaultRouter()
router.register("accounts", AccountViewSet)
router.register("periods", AccountingPeriodViewSet)
router.register("journal-entries", JournalEntryViewSet)
router.register("reports", ReportViewSet, basename="reports")

urlpatterns = router.urls
