"""Work-order completion: consume components, receive the finished product."""
from decimal import Decimal

from django.db import transaction

from apps.inventory.services import InventoryError, issue_stock, receive_stock

from .models import ZERO, WorkOrder


class ManufacturingError(Exception):
    pass


@transaction.atomic
def complete_work_order(work_order: WorkOrder) -> WorkOrder:
    """Issue every BOM component (quantity x order quantity) at its valuation
    cost and receive the finished product at the rolled-up unit cost."""
    if work_order.status != WorkOrder.Status.DRAFT:
        raise ManufacturingError(f"Work order {work_order.pk} is {work_order.status}; cannot complete.")
    company = work_order.company
    warehouse = work_order.warehouse
    total_cost = ZERO

    for line in work_order.bom.lines.select_related("component"):
        needed = (line.quantity * work_order.quantity)
        try:
            _move, cost = issue_stock(
                company=company, item=line.component, warehouse=warehouse,
                quantity=needed, date=work_order.date,
                source_type="work_order", source_id=work_order.pk,
            )
        except InventoryError as exc:
            raise ManufacturingError(str(exc)) from exc
        total_cost += cost

    unit_cost = (total_cost / work_order.quantity).quantize(Decimal("0.0001"))
    receive_stock(
        company=company, item=work_order.bom.product, warehouse=warehouse,
        quantity=work_order.quantity, unit_cost=unit_cost, date=work_order.date,
        source_type="work_order", source_id=work_order.pk,
    )
    work_order.produced_cost = total_cost.quantize(Decimal("0.01"))
    work_order.status = WorkOrder.Status.DONE
    work_order.save(update_fields=["produced_cost", "status", "updated_at"])
    return work_order
