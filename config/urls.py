from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/accounting/", include("apps.accounting.urls")),
    path("api/masterdata/", include("apps.masterdata.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/banking/", include("apps.banking.urls")),
    path("api/assets/", include("apps.assets.urls")),
    path("api/payroll/", include("apps.payroll.urls")),
    path("api/manufacturing/", include("apps.manufacturing.urls")),
]
