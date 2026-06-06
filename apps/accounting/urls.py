from rest_framework.routers import DefaultRouter

from .views import AccountingPeriodViewSet, AccountViewSet, JournalEntryViewSet

router = DefaultRouter()
router.register("accounts", AccountViewSet)
router.register("periods", AccountingPeriodViewSet)
router.register("journal-entries", JournalEntryViewSet)

urlpatterns = router.urls
