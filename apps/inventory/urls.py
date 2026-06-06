from rest_framework.routers import DefaultRouter

from .views import StockMoveViewSet

router = DefaultRouter()
router.register("stock-moves", StockMoveViewSet)

urlpatterns = router.urls
