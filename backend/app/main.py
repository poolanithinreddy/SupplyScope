import os
from contextlib import asynccontextmanager
from datetime import timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m
from .ai import optional_llm_explanation
from .database import Base, SessionLocal, engine, get_db
from .schemas import ApprovalRequest, ProposalCreate
from .seed import SCENARIO_TODAY, reset_database
from .services import active_outlooks, explanation, get_order, response_options


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.scalar(select(func.count(m.Supplier.id))):
            reset_database(db)
    yield


app = FastAPI(title="SupplyScope API", version="1.0.0", description="Deterministic disruption response for synthetic logistics data.", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

def audit(db: Session, actor: str, action: str, entity_type: str, entity_id: str, detail: str) -> None:
    db.add(m.AuditEvent(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail))


@app.get("/health")
def health():
    return {"status": "ok", "scenario_date": SCENARIO_TODAY}


@app.post("/api/scenario/reset")
def reset(db: Session = Depends(get_db)):
    reset_database(db)
    return {"status": "reset", "message": "Synthetic scenario restored."}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    outlooks = active_outlooks(db)
    risks = [o for o in outlooks if o["affected"]]
    disruptions = db.scalars(select(m.Disruption).where(m.Disruption.active.is_(True))).all()
    return {
        "company": "Northstar Freightworks", "scenario_date": SCENARIO_TODAY,
        "metrics": {"active_disruptions": len(disruptions), "orders_at_risk": len(risks), "units_exposed": sum(o["shortage"] for o in risks), "recovered": sum(o["status"] == "recovered" for o in outlooks)},
        "disruptions": [{"id": d.id, "code": d.code, "severity": d.severity, "summary": d.summary, "delay_days": d.delay_days, "shipment": d.shipment.code} for d in disruptions],
        "orders": outlooks,
    }


@app.get("/api/orders/{order_id}")
def order_detail(order_id: int, db: Session = Depends(get_db)):
    try:
        order, outlook = get_order(db, order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    outlook["options"] = response_options(db, order, outlook) if outlook["shortage"] else []
    return outlook


@app.post("/api/orders/{order_id}/explain")
def explain_order(order_id: int, db: Session = Depends(get_db)):
    try:
        _, outlook = get_order(db, order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    deterministic = explanation(outlook)
    return optional_llm_explanation(outlook, deterministic)


@app.post("/api/proposals", status_code=201)
def create_proposal(body: ProposalCreate, db: Session = Depends(get_db)):
    try:
        order, outlook = get_order(db, body.order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    option = next((o for o in response_options(db, order, outlook) if o["type"] == body.option_type and o["source_ref"] == body.source_ref), None)
    if not option or option["status"] == "infeasible":
        raise HTTPException(422, "Selected response is not currently feasible.")
    if body.quantity > option["quantity"]:
        raise HTTPException(422, "Proposal quantity exceeds currently available supply.")
    proposal = m.Proposal(order_id=body.order_id, option_type=body.option_type, source_ref=body.source_ref, quantity=body.quantity, expected_arrival=body.expected_arrival, status="pending", created_by=body.actor, rationale=body.rationale)
    db.add(proposal)
    db.flush()
    audit(db, body.actor, "proposal.created", "proposal", str(proposal.id), f"Created {body.option_type} proposal for {body.quantity} units. No inventory changed.")
    db.commit()
    db.refresh(proposal)
    return {"id": proposal.id, "status": proposal.status, "inventory_changed": False, "message": "Proposal ready for review. Inventory is unchanged."}


@app.post("/api/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int, body: ApprovalRequest, db: Session = Depends(get_db)):
    prior = db.scalar(select(m.Approval).where(m.Approval.idempotency_key == body.idempotency_key))
    if prior:
        if prior.proposal_id != proposal_id:
            raise HTTPException(409, "Idempotency key was already used for a different proposal.")
        return {"proposal_id": prior.proposal_id, "status": prior.outcome, "idempotent_replay": True}
    proposal = db.scalar(select(m.Proposal).where(m.Proposal.id == proposal_id).with_for_update())
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    if proposal.status == "approved":
        raise HTTPException(409, "Proposal has already been approved.")
    order, outlook = get_order(db, proposal.order_id)
    options = response_options(db, order, outlook)
    option = next((o for o in options if o["type"] == proposal.option_type and o["source_ref"] == proposal.source_ref), None)
    if not option or option["status"] == "infeasible" or option["available"] < proposal.quantity:
        proposal.status = "stale"
        audit(db, body.actor, "approval.rejected_stale", "proposal", str(proposal.id), "Availability recheck failed; no inventory changed.")
        db.commit()
        raise HTTPException(409, "Proposal is stale: supply is no longer available.")

    line = order.lines[0]
    audit(db, body.actor, "approval.attempted", "proposal", str(proposal.id), "Approval constraints rechecked inside transaction.")
    code_suffix = f"{proposal.id:04d}"
    if proposal.option_type == "transfer":
        inv = db.scalar(select(m.Inventory).where(m.Inventory.id == int(proposal.source_ref)).with_for_update())
        if not inv or inv.on_hand - inv.reserved < proposal.quantity:
            proposal.status = "stale"
            audit(db, body.actor, "approval.rejected_stale", "proposal", str(proposal.id), "Source stock changed during approval.")
            db.commit()
            raise HTTPException(409, "Proposal is stale: transfer stock was consumed.")
        inv.reserved += proposal.quantity
        shipment = m.InboundShipment(code=f"TRN-{code_suffix}", source_facility_id=inv.facility_id, destination_id=order.destination_facility_id, sku_id=line.sku_id, quantity=proposal.quantity, original_eta=proposal.expected_arrival, current_eta=proposal.expected_arrival, status="confirmed", shipment_type="transfer")
        db.add(shipment); db.flush()
        db.add(m.Reservation(inventory_id=inv.id, order_line_id=line.id, proposal_id=proposal.id, quantity=proposal.quantity, status="active"))
        audit(db, body.actor, "inventory.reserved", "inventory", str(inv.id), f"Reserved {proposal.quantity} units for transfer {shipment.code}.")
    else:
        cap = db.scalar(select(m.SupplierCapability).where(m.SupplierCapability.id == int(proposal.source_ref)).with_for_update())
        if not cap or cap.available_capacity < proposal.quantity:
            proposal.status = "stale"
            audit(db, body.actor, "approval.rejected_stale", "proposal", str(proposal.id), "Supplier capacity changed during approval.")
            db.commit()
            raise HTTPException(409, "Proposal is stale: supplier capacity was consumed.")
        cap.available_capacity -= proposal.quantity
        shipment = m.InboundShipment(code=f"EXP-{code_suffix}", supplier_id=cap.supplier_id, destination_id=order.destination_facility_id, sku_id=line.sku_id, quantity=proposal.quantity, original_eta=proposal.expected_arrival, current_eta=proposal.expected_arrival, status="confirmed", shipment_type="expedite")
        db.add(shipment); db.flush()
        audit(db, body.actor, "supplier.capacity_reserved", "supplier_capability", str(cap.id), f"Reserved {proposal.quantity} units for {shipment.code}.")

    remaining = proposal.quantity
    for allocation in line.allocations:
        if remaining and allocation.status == "active" and allocation.shipment and allocation.shipment.status == "delayed":
            allocation.status = "replanned"
            remaining -= allocation.quantity
    db.add(m.Allocation(order_line_id=line.id, shipment_id=shipment.id, quantity=proposal.quantity, status="active"))
    proposal.status = "approved"
    order.status = "recovered"
    db.add(m.Approval(proposal_id=proposal.id, actor=body.actor, idempotency_key=body.idempotency_key, outcome="approved"))
    audit(db, body.actor, "proposal.approved", "proposal", str(proposal.id), f"Approved and scheduled {shipment.code}; order outlook recalculated.")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Approval conflicted with a concurrent request.") from exc
    db.expire_all()
    _, updated = get_order(db, order.id)
    return {"proposal_id": proposal.id, "status": "approved", "shipment": shipment.code, "order_outlook": updated}


@app.get("/api/audit")
def audit_log(db: Session = Depends(get_db)):
    events = db.scalars(select(m.AuditEvent).order_by(m.AuditEvent.created_at.desc()).limit(100)).all()
    return [{"id": e.id, "actor": e.actor, "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id, "detail": e.detail, "created_at": e.created_at.replace(tzinfo=e.created_at.tzinfo or timezone.utc)} for e in events]
