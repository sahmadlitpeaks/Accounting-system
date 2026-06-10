from rest_framework.routers import DefaultRouter

from .views import BankAccountViewSet, BankStatementViewSet

router = DefaultRouter()
router.register("accounts", BankAccountViewSet)
router.register("statements", BankStatementViewSet)

urlpatterns = router.urls
