from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from .access import user_company_ids
from .models import AuditLog, Membership
from .permissions import CompanyScopedQuerysetMixin
from .serializers import AuditLogSerializer, MembershipSerializer


class MembershipViewSet(viewsets.ModelViewSet):
    queryset = Membership.objects.select_related("user", "company").all()
    serializer_class = MembershipSerializer
    permission_classes = [IsAdminUser]


class AuditLogViewSet(CompanyScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["company", "action", "model"]
