from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalStatus, CaseState, Severity
from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Item(Base, TimestampMixin):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(240))
    base_uom: Mapped[str | None] = mapped_column(String(12))
    manufacturer_part_number: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE")
    revision: Mapped[str] = mapped_column(String(12), default="A")


class ItemRevision(Base, TimestampMixin):
    __tablename__ = "item_revisions"
    __table_args__ = (UniqueConstraint("item_id", "revision", name="uq_item_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    revision: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class BOM(Base, TimestampMixin):
    __tablename__ = "boms"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    parent_item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    revision: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE")
    lines: Mapped[list[BOMLine]] = relationship(cascade="all, delete-orphan")


class BOMLine(Base, TimestampMixin):
    __tablename__ = "bom_lines"
    __table_args__ = (UniqueConstraint("bom_id", "position", name="uq_bom_position"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    bom_id: Mapped[str] = mapped_column(ForeignKey("boms.id"), index=True)
    position: Mapped[int]
    component_item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    uom: Mapped[str] = mapped_column(String(12))
    component_revision: Mapped[str | None] = mapped_column(String(12))


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovedVendor(Base, TimestampMixin):
    __tablename__ = "approved_vendors"
    __table_args__ = (UniqueConstraint("item_id", "supplier_id", name="uq_approved_vendor"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    approved: Mapped[bool] = mapped_column(Boolean, default=True)


class SupplierItem(Base, TimestampMixin):
    __tablename__ = "supplier_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    supplier_part_number: Mapped[str] = mapped_column(String(80), index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)


class PackagingProfile(Base, TimestampMixin):
    __tablename__ = "packaging_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_item_id: Mapped[int] = mapped_column(ForeignKey("supplier_items.id"))
    package_quantity: Mapped[int]
    moq: Mapped[int]
    purchasing_uom: Mapped[str] = mapped_column(String(12))
    conversion_factor: Mapped[float] = mapped_column(Float, default=1)


class Routing(Base, TimestampMixin):
    __tablename__ = "routings"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    revision: Mapped[str] = mapped_column(String(12))


class RoutingOperation(Base, TimestampMixin):
    __tablename__ = "routing_operations"
    id: Mapped[int] = mapped_column(primary_key=True)
    routing_id: Mapped[str] = mapped_column(ForeignKey("routings.id"))
    sequence: Mapped[int]
    work_center: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    status: Mapped[str] = mapped_column(String(24), default="OPEN")


class PurchaseOrderLine(Base, TimestampMixin):
    __tablename__ = "purchase_order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int]
    uom: Mapped[str] = mapped_column(String(12), default="EA")


class WorkOrder(Base, TimestampMixin):
    __tablename__ = "work_orders"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int]
    status: Mapped[str] = mapped_column(String(24), default="RELEASED")


class InventoryBalance(Base, TimestampMixin):
    __tablename__ = "inventory_balances"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    location: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[float]


class CustomerOrder(Base, TimestampMixin):
    __tablename__ = "customer_orders"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="OPEN")


class CustomerOrderLine(Base, TimestampMixin):
    __tablename__ = "customer_order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_order_id: Mapped[str] = mapped_column(ForeignKey("customer_orders.id"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int]
    promise_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EngineeringChangeOrder(Base, TimestampMixin):
    __tablename__ = "engineering_change_orders"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24))


class ReleasePacket(Base, TimestampMixin):
    __tablename__ = "release_packets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80))
    content_hash: Mapped[str] = mapped_column(String(64))
    release_type: Mapped[str] = mapped_column(String(40))
    product: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(40), default=CaseState.RECEIVED)
    severity: Mapped[str] = mapped_column(String(20), default=Severity.INFO)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    approval_status: Mapped[str | None] = mapped_column(String(30))
    scenario_key: Mapped[str] = mapped_column(String(60), index=True)
    __table_args__ = (UniqueConstraint("source_id", "content_hash", name="uq_packet_source_hash"),)


class ReleaseDocument(Base, TimestampMixin):
    __tablename__ = "release_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    filename: Mapped[str] = mapped_column(String(180))
    source_type: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64))
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)


class ExtractionResult(Base, TimestampMixin):
    __tablename__ = "extraction_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80))
    value: Mapped[Any | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    model_generated: Mapped[bool] = mapped_column(Boolean, default=False)


class ValidationFinding(Base, TimestampMixin):
    __tablename__ = "validation_findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)
    affected_record: Mapped[str] = mapped_column(String(120))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    current_value: Mapped[Any | None] = mapped_column(JSON)
    candidate_value: Mapped[Any | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    suggested_action: Mapped[str] = mapped_column(String(160))
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class DuplicateCandidate(Base, TimestampMixin):
    __tablename__ = "duplicate_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    candidate_item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    score: Mapped[float]
    reasons: Mapped[list[str]] = mapped_column(JSON)
    resolution: Mapped[str | None] = mapped_column(String(40))


class ImpactRecord(Base, TimestampMixin):
    __tablename__ = "impact_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    impact_type: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(20))
    graph_path: Mapped[list[str]] = mapped_column(JSON, default=list)


class ProposedChangeSet(Base, TimestampMixin):
    __tablename__ = "proposed_change_sets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    case_version: Mapped[int]
    digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="STAGED")


class ProposedChange(Base, TimestampMixin):
    __tablename__ = "proposed_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_set_id: Mapped[str] = mapped_column(ForeignKey("proposed_change_sets.id"), index=True)
    action_class: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(60))
    field_name: Mapped[str] = mapped_column(String(80))
    before_value: Mapped[Any | None] = mapped_column(JSON)
    after_value: Mapped[Any | None] = mapped_column(JSON)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    change_set_id: Mapped[str] = mapped_column(ForeignKey("proposed_change_sets.id"))
    required_role: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    case_version: Mapped[int]
    status: Mapped[str] = mapped_column(String(30), default=ApprovalStatus.PENDING)


class ApprovalDecision(Base, TimestampMixin):
    __tablename__ = "approval_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    approval_request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    rationale: Mapped[str] = mapped_column(Text)


class PostingTransaction(Base, TimestampMixin):
    __tablename__ = "posting_transactions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    records_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("release_packets.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str] = mapped_column(String(80))
    service: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64))
    previous_state: Mapped[str | None] = mapped_column(String(40))
    new_state: Mapped[str | None] = mapped_column(String(40))
    before_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    approval_reference: Mapped[str | None] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(30))
    error_information: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str] = mapped_column(String(40), index=True)


class Escalation(Base, TimestampMixin):
    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("release_packets.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    assigned_role: Mapped[str] = mapped_column(String(80))
