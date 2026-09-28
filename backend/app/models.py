from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(80))


class Facility(Base, TimestampMixin):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    transfer_lead_days: Mapped[int] = mapped_column(Integer, default=2)


class SKU(Base, TimestampMixin):
    __tablename__ = "skus"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(140))
    unit: Mapped[str] = mapped_column(String(20), default="units")


class SupplierCapability(Base, TimestampMixin):
    __tablename__ = "supplier_capabilities"
    __table_args__ = (
        UniqueConstraint("supplier_id", "sku_id", name="uq_supplier_sku"),
        CheckConstraint("available_capacity >= 0", name="ck_capability_capacity_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), index=True)
    available_capacity: Mapped[int] = mapped_column(Integer)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    supplier: Mapped[Supplier] = relationship()


class Inventory(Base, TimestampMixin):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("facility_id", "sku_id", name="uq_inventory_facility_sku"),
        CheckConstraint("on_hand >= 0 AND reserved >= 0 AND reserved <= on_hand", name="ck_inventory_balance"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"), index=True)
    on_hand: Mapped[int] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    facility: Mapped[Facility] = relationship()
    sku: Mapped[SKU] = relationship()


class InboundShipment(Base, TimestampMixin):
    __tablename__ = "inbound_shipments"
    __table_args__ = (Index("ix_shipments_destination_eta", "destination_id", "current_eta"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    source_facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    original_eta: Mapped[date] = mapped_column(Date)
    current_eta: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), index=True)
    shipment_type: Mapped[str] = mapped_column(String(24), default="supplier")
    supplier: Mapped[Optional[Supplier]] = relationship(foreign_keys=[supplier_id])
    source_facility: Mapped[Optional[Facility]] = relationship(foreign_keys=[source_facility_id])
    destination: Mapped[Facility] = relationship(foreign_keys=[destination_id])
    sku: Mapped[SKU] = relationship()


class CustomerOrder(Base, TimestampMixin):
    __tablename__ = "customer_orders"
    __table_args__ = (Index("ix_orders_status_promised", "status", "promised_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    destination_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    promised_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True, default="open")
    destination: Mapped[Facility] = relationship()
    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base, TimestampMixin):
    __tablename__ = "order_lines"
    __table_args__ = (UniqueConstraint("order_id", "sku_id", name="uq_order_sku"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    order: Mapped[CustomerOrder] = relationship(back_populates="lines")
    sku: Mapped[SKU] = relationship()
    allocations: Mapped[list["Allocation"]] = relationship(back_populates="order_line", cascade="all, delete-orphan")


class Allocation(Base, TimestampMixin):
    __tablename__ = "allocations"
    __table_args__ = (Index("ix_allocations_line_status", "order_line_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id", ondelete="CASCADE"))
    inventory_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inventory.id"), nullable=True)
    shipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inbound_shipments.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="active")
    order_line: Mapped[OrderLine] = relationship(back_populates="allocations")
    inventory: Mapped[Optional[Inventory]] = relationship()
    shipment: Mapped[Optional[InboundShipment]] = relationship()


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservations"
    __table_args__ = (UniqueConstraint("proposal_id", name="uq_reservation_proposal"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"), index=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"), index=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="active")


class Disruption(Base, TimestampMixin):
    __tablename__ = "disruptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("inbound_shipments.id"), index=True)
    disruption_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    summary: Mapped[str] = mapped_column(String(220))
    delay_days: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True, index=True)
    shipment: Mapped[InboundShipment] = relationship()


class Proposal(Base, TimestampMixin):
    __tablename__ = "proposals"
    __table_args__ = (Index("ix_proposals_order_status", "order_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id"), index=True)
    option_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    expected_arrival: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_by: Mapped[str] = mapped_column(String(100))
    rationale: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_approval_proposal"),
        UniqueConstraint("idempotency_key", name="uq_approval_idempotency"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(24))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_created_action", "created_at", "action"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
