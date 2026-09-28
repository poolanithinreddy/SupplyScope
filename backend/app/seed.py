from datetime import date

from sqlalchemy.orm import Session

from . import models as m
from .database import Base, engine


SCENARIO_TODAY = date(2026, 9, 28)


def reset_database(db: Session) -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    suppliers = [
        m.Supplier(id=1, code="SUP-MER", name="Meridian Components", region="Penang, MY"),
        m.Supplier(id=2, code="SUP-NOR", name="Northstar Industrial", region="Monterrey, MX"),
        m.Supplier(id=3, code="SUP-EAS", name="Eastline Works", region="Columbus, OH"),
    ]
    facilities = [
        m.Facility(id=1, code="EWR-01", name="Harborpoint East", city="Newark, NJ", transfer_lead_days=1),
        m.Facility(id=2, code="DFW-02", name="Crosswind Central", city="Dallas, TX", transfer_lead_days=2),
    ]
    skus = [
        m.SKU(id=1, code="AX-440", name="Axis control module"),
        m.SKU(id=2, code="LM-210", name="Lumen sensor pack"),
        m.SKU(id=3, code="VT-800", name="Vector drive unit"),
    ]
    db.add_all(suppliers + facilities + skus)
    db.flush()
    db.add_all([
        m.SupplierCapability(id=1, supplier_id=1, sku_id=1, available_capacity=120, lead_time_days=9),
        m.SupplierCapability(id=2, supplier_id=2, sku_id=1, available_capacity=90, lead_time_days=5),
        m.SupplierCapability(id=3, supplier_id=3, sku_id=1, available_capacity=18, lead_time_days=4),
        m.SupplierCapability(id=4, supplier_id=2, sku_id=2, available_capacity=70, lead_time_days=6),
        m.SupplierCapability(id=5, supplier_id=1, sku_id=3, available_capacity=40, lead_time_days=10),
    ])
    db.add_all([
        m.Inventory(id=1, facility_id=1, sku_id=1, on_hand=55, reserved=45),
        m.Inventory(id=2, facility_id=2, sku_id=1, on_hand=95, reserved=35),
        m.Inventory(id=3, facility_id=1, sku_id=2, on_hand=80, reserved=20),
        m.Inventory(id=4, facility_id=2, sku_id=2, on_hand=45, reserved=15),
        m.Inventory(id=5, facility_id=1, sku_id=3, on_hand=22, reserved=4),
        m.Inventory(id=6, facility_id=2, sku_id=3, on_hand=35, reserved=10),
    ])
    shipments = [
        m.InboundShipment(id=1, code="INB-7392", supplier_id=1, destination_id=1, sku_id=1, quantity=80, original_eta=date(2026, 10, 1), current_eta=date(2026, 10, 10), status="delayed", shipment_type="supplier"),
        m.InboundShipment(id=2, code="INB-7410", supplier_id=2, destination_id=1, sku_id=2, quantity=60, original_eta=date(2026, 10, 3), current_eta=date(2026, 10, 3), status="confirmed", shipment_type="supplier"),
        m.InboundShipment(id=3, code="INB-7418", supplier_id=3, destination_id=2, sku_id=3, quantity=30, original_eta=date(2026, 10, 5), current_eta=date(2026, 10, 5), status="confirmed", shipment_type="supplier"),
    ]
    db.add_all(shipments)
    orders = [
        m.CustomerOrder(id=1, code="ORD-4821", customer_name="Atlas Field Systems", destination_facility_id=1, promised_date=date(2026, 10, 5), priority="critical", status="open"),
        m.CustomerOrder(id=2, code="ORD-4824", customer_name="Kestrel Automation", destination_facility_id=1, promised_date=date(2026, 10, 7), priority="high", status="open"),
        m.CustomerOrder(id=3, code="ORD-4830", customer_name="Juniper Controls", destination_facility_id=1, promised_date=date(2026, 10, 8), priority="standard", status="open"),
        m.CustomerOrder(id=4, code="ORD-4799", customer_name="Solace Robotics", destination_facility_id=2, promised_date=date(2026, 9, 26), priority="high", status="fulfilled"),
        m.CustomerOrder(id=5, code="ORD-4804", customer_name="Bluebird Energy", destination_facility_id=2, promised_date=date(2026, 10, 2), priority="standard", status="cancelled"),
    ]
    db.add_all(orders)
    db.flush()
    lines = [
        m.OrderLine(id=1, order_id=1, sku_id=1, quantity=50),
        m.OrderLine(id=2, order_id=2, sku_id=1, quantity=30),
        m.OrderLine(id=3, order_id=3, sku_id=2, quantity=20),
        m.OrderLine(id=4, order_id=4, sku_id=3, quantity=12),
        m.OrderLine(id=5, order_id=5, sku_id=1, quantity=10),
    ]
    db.add_all(lines)
    db.flush()
    db.add_all([
        m.Allocation(order_line_id=1, inventory_id=1, quantity=10, status="active"),
        m.Allocation(order_line_id=1, shipment_id=1, quantity=40, status="active"),
        m.Allocation(order_line_id=2, inventory_id=1, quantity=5, status="active"),
        m.Allocation(order_line_id=2, shipment_id=1, quantity=25, status="active"),
        m.Allocation(order_line_id=3, inventory_id=3, quantity=20, status="active"),
        m.Allocation(order_line_id=4, inventory_id=6, quantity=12, status="consumed"),
        m.Allocation(order_line_id=5, inventory_id=2, quantity=10, status="released"),
    ])
    db.add(m.Disruption(id=1, code="DSP-018", shipment_id=1, disruption_type="port_congestion", severity="high", summary="Port congestion moved inbound INB-7392 nine days", delay_days=9, active=True))
    db.add(m.AuditEvent(actor="system", action="scenario.reset", entity_type="scenario", entity_id="northstar-demo", detail="Synthetic Northstar Freightworks demo scenario restored to baseline."))
    db.commit()
