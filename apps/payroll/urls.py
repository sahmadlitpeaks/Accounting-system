from rest_framework.routers import DefaultRouter

from .views import EmployeeViewSet, PayrollRunViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet)
router.register("runs", PayrollRunViewSet)

urlpatterns = router.urls
