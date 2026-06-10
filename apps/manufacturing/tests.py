from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.core.models import Company, Currency
from apps.inventory.services import receive_stock, stock_on_hand, stock_value
from apps.masterdata.models import Item, UnitOfMeasure, Warehouse

from .models import BillOfMaterial, BOMLine, WorkOrder
from .services import ManufacturingError, complete_work_order


class ManufacturingTests(TestCase):
    def setUp(self):
        cur = Currency.objects.create(code="PKR", name="Rupee")
        self.company = Company.objects.create(name="Lahore", country_code="PK", base_currency=cur)
        seed_chart_of_accounts(self.company)
        uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        self.wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")
        self.frame = Item.objects.create(company=self.company, sku="FRAME", name="Frame", uom=uom)
        self.wheel = Item.objects.create(company=self.company, sku="WHEEL", name="Wheel", uom=uom)
        self.bike = Item.objects.create(company=self.company, sku="BIKE", name="Bicycle", uom=uom)
        self.bom = BillOfMaterial.objects.create(company=self.company, product=self.bike)
        BOMLine.objects.create(bom=self.bom, component=self.frame, quantity=Decimal("1"))
        BOMLine.objects.create(bom=self.bom, component=self.wheel, quantity=Decimal("2"))
        receive_stock(company=self.company, item=self.frame, warehouse=self.wh,
                      quantity=10, unit_cost=Decimal("100"), date=date.today())
        receive_stock(company=self.company, item=self.wheel, warehouse=self.wh,
                      quantity=20, unit_cost=Decimal("25"), date=date.today())

    def test_complete_work_order_rolls_up_cost(self):
        wo = WorkOrder.objects.create(company=self.company, bom=self.bom,
                                      warehouse=self.wh, quantity=Decimal("5"), date=date.today())
        complete_work_order(wo)
        wo.refresh_from_db()
        # Per bike: 1 frame @100 + 2 wheels @25 = 150. Five bikes = 750.
        self.assertEqual(wo.status, WorkOrder.Status.DONE)
        self.assertEqual(wo.produced_cost, Decimal("750.00"))
        self.assertEqual(stock_on_hand(self.frame), Decimal("5.0000"))
        self.assertEqual(stock_on_hand(self.wheel), Decimal("10.0000"))
        self.assertEqual(stock_on_hand(self.bike), Decimal("5.0000"))
        self.assertEqual(stock_value(self.bike), Decimal("750.00"))
        # Total inventory value conserved: 10*100 + 20*25 = 1500 before and after.
        total = stock_value(self.frame) + stock_value(self.wheel) + stock_value(self.bike)
        self.assertEqual(total, Decimal("1500.00"))

    def test_insufficient_components_rejected(self):
        wo = WorkOrder.objects.create(company=self.company, bom=self.bom,
                                      warehouse=self.wh, quantity=Decimal("50"), date=date.today())
        with self.assertRaises(ManufacturingError):
            complete_work_order(wo)
        wo.refresh_from_db()
        self.assertEqual(wo.status, WorkOrder.Status.DRAFT)
        # Nothing consumed (atomic rollback).
        self.assertEqual(stock_on_hand(self.frame), Decimal("10.0000"))

    def test_cannot_complete_twice(self):
        wo = WorkOrder.objects.create(company=self.company, bom=self.bom,
                                      warehouse=self.wh, quantity=Decimal("1"), date=date.today())
        complete_work_order(wo)
        with self.assertRaises(ManufacturingError):
            complete_work_order(wo)
