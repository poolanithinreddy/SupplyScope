from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models as m
from .seed import SCENARIO_TODAY


PRIORITY_WEIGHT = {"critical": 35, "high": 24, "standard": 12}


def _orders_query():
    return select(m.CustomerOrder).options(
        selectinload(m.CustomerOrder.destination),
        selectinload(m.CustomerOrder.lines).selectinload(m.OrderLine.sku),
        selectinload(m.CustomerOrder.lines).selectinload(m.OrderLine.allocations).selectinload(m.Allocation.inventory).selectinload(m.Inventory.facility),
        selectinload(m.CustomerOrder.lines).selectinload(m.OrderLine.allocations).selectinload(m.Allocation.shipment).selectinload(m.InboundShipment.supplier),
    )


def order_outlook(order: m.CustomerOrder) -> dict:
    line = order.lines[0]
    active = [a for a in line.allocations if a.status == "active"]
    on_time = 0
    eventually = 0
    sources = []
    arrivals: list[date] = []
    for allocation in active:
        eventually += allocation.quantity
        if allocation.inventory_id:
            on_time += allocation.quantity
            sources.append({"type": "inventory", "code": allocation.inventory.facility.code, "quantity": allocation.quantity, "arrival": SCENARIO_TODAY.isoformat(), "status": "ready"})
        elif allocation.shipment:
            shipment = allocation.shipment
            arrivals.append(shipment.current_eta)
            if shipment.current_eta <= order.promised_date:
                on_time += allocation.quantity
            sources.append({"type": "shipment", "code": shipment.code, "quantity": allocation.quantity, "arrival": shipment.current_eta.isoformat(), "original_arrival": shipment.original_eta.isoformat(), "status": shipment.status, "supplier": shipment.supplier.name if shipment.supplier else shipment.source_facility.name})
    shortage = max(0, line.quantity - on_time)
    projected = SCENARIO_TODAY if on_time >= line.quantity else (max(arrivals) if eventually >= line.quantity and arrivals else None)
    late_days = max(0, (projected - order.promised_date).days) if projected else 30
    shortage_ratio = shortage / line.quantity
    deadline_pressure = max(0, 20 - max(0, (order.promised_date - SCENARIO_TODAY).days) * 2)
    urgency = round(PRIORITY_WEIGHT[order.priority] + shortage_ratio * 35 + late_days * 6 + deadline_pressure)
    return {
        "id": order.id, "code": order.code, "customer": order.customer_name, "priority": order.priority,
        "status": order.status, "facility": order.destination.name, "facility_code": order.destination.code,
        "promised_date": order.promised_date.isoformat(), "sku": line.sku.code, "sku_name": line.sku.name,
        "quantity": line.quantity, "available_by_promise": on_time, "shortage": shortage,
        "projected_date": projected.isoformat() if projected else None, "late_days": late_days,
        "urgency_score": urgency, "affected": shortage > 0, "sources": sources,
        "calculation": {
            "formula": "priority weight + shortage ratio × 35 + projected late days × 6 + deadline pressure",
            "priority_weight": PRIORITY_WEIGHT[order.priority], "shortage_ratio": round(shortage_ratio, 2),
            "late_day_points": late_days * 6, "deadline_pressure": deadline_pressure,
        },
    }


def active_outlooks(db: Session) -> list[dict]:
    orders = db.scalars(_orders_query().where(m.CustomerOrder.status.in_(["open", "recovered"]))).all()
    return sorted((order_outlook(o) for o in orders), key=lambda x: x["urgency_score"], reverse=True)


def get_order(db: Session, order_id: int) -> tuple[m.CustomerOrder, dict]:
    order = db.scalar(_orders_query().where(m.CustomerOrder.id == order_id))
    if not order:
        raise LookupError("Order not found")
    return order, order_outlook(order)


def response_options(db: Session, order: m.CustomerOrder, outlook: dict) -> list[dict]:
    line = order.lines[0]
    needed = outlook["shortage"]
    results = []
    inventories = db.scalars(select(m.Inventory).options(selectinload(m.Inventory.facility)).where(m.Inventory.sku_id == line.sku_id, m.Inventory.facility_id != order.destination_facility_id)).all()
    for inv in inventories:
        available = inv.on_hand - inv.reserved
        arrival = SCENARIO_TODAY + timedelta(days=inv.facility.transfer_lead_days)
        enough = available >= needed and needed > 0
        results.append({
            "id": f"transfer:{inv.id}", "type": "transfer", "source_ref": str(inv.id),
            "title": f"Transfer from {inv.facility.name}", "source": inv.facility.code,
            "quantity": min(available, needed), "available": available, "expected_arrival": arrival.isoformat(),
            "delivery_impact": "On time" if arrival <= order.promised_date else f"{(arrival-order.promised_date).days} days late",
            "status": "on_time" if enough and arrival <= order.promised_date else ("late" if enough else "infeasible"),
            "reason": None if enough else f"Only {available} unreserved units are available; {needed} are required.",
        })
    capabilities = db.scalars(select(m.SupplierCapability).options(selectinload(m.SupplierCapability.supplier)).where(m.SupplierCapability.sku_id == line.sku_id)).all()
    for cap in capabilities:
        arrival = SCENARIO_TODAY + timedelta(days=cap.lead_time_days)
        enough = cap.available_capacity >= needed and needed > 0
        results.append({
            "id": f"supplier:{cap.id}", "type": "supplier", "source_ref": str(cap.id),
            "title": f"Expedite from {cap.supplier.name}", "source": cap.supplier.code,
            "quantity": min(cap.available_capacity, needed), "available": cap.available_capacity,
            "expected_arrival": arrival.isoformat(),
            "delivery_impact": "On time" if arrival <= order.promised_date else f"{(arrival-order.promised_date).days} days late",
            "status": "on_time" if enough and arrival <= order.promised_date else ("late" if enough else "infeasible"),
            "reason": None if enough else f"Supplier capacity is {cap.available_capacity} units; {needed} are required.",
        })
    rank = {"on_time": 0, "late": 1, "infeasible": 2}
    return sorted(results, key=lambda x: (rank[x["status"]], x["expected_arrival"]))


def explanation(outlook: dict) -> dict:
    delayed = next((s for s in outlook["sources"] if s["type"] == "shipment" and s["status"] == "delayed"), None)
    if not delayed:
        answer = f"{outlook['code']} is currently covered by supply available before its promise date."
    else:
        answer = (
            f"{outlook['code']} needs {outlook['quantity']} {outlook['sku']} units, but only "
            f"{outlook['available_by_promise']} are available by {outlook['promised_date']}. "
            f"The remaining {outlook['shortage']} units are allocated to {delayed['code']}, now due "
            f"{delayed['arrival']}. That moves the projected fulfillment {outlook['late_days']} days past promise."
        )
    return {"answer": answer, "mode": "deterministic", "links": [
        {"label": outlook["code"], "href": f"#order-{outlook['id']}"},
        {"label": outlook["sku"], "href": f"#sku-{outlook['sku']}"},
        *([{"label": delayed["code"], "href": f"#shipment-{delayed['code']}"}] if delayed else []),
    ]}
