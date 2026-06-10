from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})


def index(_request):
    """Friendly API index so the bare host URL is navigable, not a 404."""
    return JsonResponse({
        "service": "Accounting System API",
        "admin": "/admin/",
        "health": "/health/",
        "frontend_dev": "http://localhost:3000",
        "apis": {
            "auth_token": "/api/accounts/token/",
            "accounting": "/api/accounting/",
            "masterdata": "/api/masterdata/",
            "inventory": "/api/inventory/",
            "orders": "/api/orders/",
            "banking": "/api/banking/",
            "assets": "/api/assets/",
            "payroll": "/api/payroll/",
            "manufacturing": "/api/manufacturing/",
        },
        "reports": {
            "trial_balance": "/api/accounting/journal-entries/trial-balance/?company=<id>",
            "profit_and_loss": "/api/accounting/reports/profit-and-loss/?company=<id>",
            "balance_sheet": "/api/accounting/reports/balance-sheet/?company=<id>",
            "tax_return": "/api/accounting/reports/tax-return/?company=<id>&start=&end=",
            "ar_aging": "/api/orders/reports/ar-aging/?company=<id>",
            "stock_valuation": "/api/inventory/stock-moves/valuation/?company=<id>",
        },
    })


urlpatterns = [
    path("", index, name="index"),
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
