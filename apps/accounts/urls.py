from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import AuditLogViewSet, MembershipViewSet

router = DefaultRouter()
router.register("memberships", MembershipViewSet)
router.register("audit-logs", AuditLogViewSet)

urlpatterns = [
    path("token/", obtain_auth_token, name="api-token"),
] + router.urls
