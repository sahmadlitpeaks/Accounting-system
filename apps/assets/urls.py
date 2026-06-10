from rest_framework.routers import DefaultRouter

from .views import AssetCategoryViewSet, FixedAssetViewSet

router = DefaultRouter()
router.register("categories", AssetCategoryViewSet)
router.register("fixed-assets", FixedAssetViewSet)

urlpatterns = router.urls
