from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.enums import ApprovalStatus, CaseState, Role, Severity
from app.db.session import Base, engine
from app.models.entities import (
    BOM,
    ApprovalRequest,
    ApprovedVendor,
    AuditEvent,
    BOMLine,
    CustomerOrder,
    CustomerOrderLine,
    DuplicateCandidate,
    EngineeringChangeOrder,
    ExtractionResult,
    ImpactRecord,
    InventoryBalance,
    Item,
    ItemRevision,
    PackagingProfile,
    ProposedChange,
    ProposedChangeSet,
    PurchaseOrder,
    PurchaseOrderLine,
    ReleaseDocument,
    ReleasePacket,
    Routing,
    RoutingOperation,
    Supplier,
    SupplierItem,
    User,
    ValidationFinding,
    WorkOrder,
)

NOTICE = "Synthetic portfolio demonstration data — not a real company record."

SCENARIOS = [
    (
        "new-pump",
        "CASE-001",
        "New item release",
        "NIS-PA-900 Pump Assembly",
        CaseState.APPROVAL_PENDING,
        Severity.ERROR,
    ),
    (
        "package-change",
        "CASE-002",
        "Supplier change",
        "NIS-SEAL-220 Cartridge Seal",
        CaseState.APPROVAL_PENDING,
        Severity.WARNING,
    ),
    (
        "obsolete-revision",
        "CASE-003",
        "Engineering change",
        "Seal revision B → C",
        CaseState.REVIEW_REQUIRED,
        Severity.ERROR,
    ),
    (
        "circular-bom",
        "CASE-004",
        "BOM release",
        "Recirculation Skid Assembly",
        CaseState.VALIDATION_FAILED,
        Severity.HARD_STOP,
    ),
    (
        "ambiguous-duplicate",
        "CASE-005",
        "Item setup",
        "316SS Pump Housing",
        CaseState.ESCALATED,
        Severity.HARD_STOP,
    ),
]

RULES = [
    ("ITEM-001", "Missing required item fields"),
    ("ITEM-002", "Duplicate manufacturer part number"),
    ("ITEM-003", "Near-duplicate item description"),
    ("ITEM-004", "Conflicting internal item number"),
    ("UOM-001", "Invalid or missing base UOM"),
    ("UOM-002", "Purchasing UOM conversion is incompatible"),
    ("PKG-001", "Supplier package quantity is outdated"),
    ("PKG-002", "Open order violates the new MOQ"),
    ("BOM-001", "BOM line quantity differs from engineering evidence"),
    ("BOM-002", "Duplicate BOM position"),
    ("BOM-003", "Circular BOM reference"),
    ("BOM-004", "Obsolete component is used in an active BOM"),
    ("REV-001", "Component revision conflict"),
    ("AVL-001", "Approved vendor is missing"),
    ("SUP-001", "Supplier-item association references an inactive supplier"),
    ("SUP-002", "Lead time is outside configured limits"),
    ("RTG-001", "Routing references an inactive work center"),
    ("IMP-001", "Engineering release affects open purchase orders"),
    ("IMP-002", "Engineering release affects work in process"),
    ("IMP-003", "Engineering release affects customer commitments"),
]


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def reset_database() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_database(db: Session) -> dict[str, int]:
    reset_database()
    users = [
        User(id="user-coordinator", name="Maya Chen", role=Role.COORDINATOR),
        User(id="user-master", name="Luis Ortega", role=Role.MASTER_DATA),
        User(id="user-planner", name="Avery Brooks", role=Role.PLANNER),
        User(id="user-procurement", name="Priya Shah", role=Role.PROCUREMENT),
        User(id="user-engineer", name="Noah Williams", role=Role.MANUFACTURING),
        User(id="user-approver", name="Jordan Kim", role=Role.APPROVER),
        User(id="user-admin", name="Sam Rivera", role=Role.ADMIN),
        User(id="user-auditor", name="Taylor Reed", role=Role.AUDITOR),
    ]
    db.add_all(users)
    suppliers = [
        Supplier(id=f"SUP-{i:03}", name=f"Northstar Demo Supplier {i:02}", active=i != 18)
        for i in range(1, 19)
    ]
    db.add_all(suppliers)
    items = []
    for i in range(1, 301):
        items.append(
            Item(
                id=f"ITEM-{i:04}",
                number=f"NIS-{i:06}",
                description=f"Industrial fluid handling component {i:03}",
                base_uom="EA",
                manufacturer_part_number=f"MPN-{i:06}",
                status="OBSOLETE" if i in {42, 87} else "ACTIVE",
                revision="B" if i == 42 else "A",
            )
        )
    items[118].description = "316 stainless steel pump housing machined"
    items[119].description = "Pump housing, machined, 316 SS"
    items[219].description = "Cartridge seal assembly 45 mm"
    db.add_all(items)
    db.flush()
    db.add_all(
        [
            ItemRevision(
                item_id=item.id,
                revision=item.revision,
                status=item.status,
                attributes={"regulated": False},
            )
            for item in items
        ]
    )
    for i in range(1, 46):
        bom = BOM(id=f"BOM-{i:03}", parent_item_id=f"ITEM-{i:04}", revision="A")
        db.add(bom)
        for pos in range(1, 4):
            component = ((i * 5 + pos) % 250) + 46
            db.add(
                BOMLine(
                    bom_id=bom.id,
                    position=pos * 10,
                    component_item_id=f"ITEM-{component:04}",
                    quantity=float(pos),
                    uom="EA",
                    component_revision="A",
                )
            )
    for i in range(1, 21):
        routing = Routing(id=f"RTG-{i:03}", item_id=f"ITEM-{i:04}", revision="A")
        db.add(routing)
        db.add(
            RoutingOperation(
                routing_id=routing.id, sequence=10, work_center=f"WC-{i % 5 + 1}", active=i != 20
            )
        )
    supplier_items = []
    for i in range(1, 41):
        supplier_id = f"SUP-{(i - 1) % 18 + 1:03}"
        item_id = f"ITEM-{i + 100:04}"
        db.add(ApprovedVendor(item_id=item_id, supplier_id=supplier_id, approved=True))
        si = SupplierItem(
            item_id=item_id,
            supplier_id=supplier_id,
            supplier_part_number=f"NSP-{i:05}",
            lead_time_days=14 + i % 20,
        )
        db.add(si)
        supplier_items.append(si)
    db.flush()
    for si in supplier_items:
        db.add(
            PackagingProfile(
                supplier_item_id=si.id,
                package_quantity=20,
                moq=100,
                purchasing_uom="PK",
                conversion_factor=20,
            )
        )
    for i in range(1, 36):
        db.add(
            InventoryBalance(
                item_id=f"ITEM-{i + 30:04}", location="NIS-PLANT-01", quantity=float(25 + i * 3)
            )
        )
    for i in range(1, 61):
        db.add(
            WorkOrder(
                id=f"WO-{i:05}", item_id=f"ITEM-{i % 45 + 1:04}", quantity=5 + i, status="RELEASED"
            )
        )
    for i in range(1, 31):
        db.add(
            EngineeringChangeOrder(
                id=f"ECO-{i:04}", title=f"Synthetic engineering change {i:02}", status="RELEASED"
            )
        )
    po_line = 0
    for i in range(1, 36):
        po = PurchaseOrder(id=f"PO-{i:05}", supplier_id=f"SUP-{(i - 1) % 18 + 1:03}")
        db.add(po)
        for _ in range(2):
            po_line += 1
            db.add(
                PurchaseOrderLine(
                    purchase_order_id=po.id,
                    item_id=f"ITEM-{100 + po_line % 40 + 1:04}",
                    quantity=100 + (po_line % 7) * 10,
                    uom="EA",
                )
            )
    for i in range(1, 26):
        order = CustomerOrder(id=f"SO-{i:05}", customer_name=f"Fictional Customer {i:02}")
        db.add(order)
        db.add(
            CustomerOrderLine(
                customer_order_id=order.id,
                item_id=f"ITEM-{i % 45 + 1:04}",
                quantity=2 + i,
                promise_date=datetime.now(UTC) + timedelta(days=i),
            )
        )
    db.flush()

    scenario_rules = {
        "new-pump": ["ITEM-003", "UOM-001", "BOM-001", "AVL-001"],
        "package-change": ["PKG-001", "PKG-002", "IMP-001"],
        "obsolete-revision": ["BOM-004", "REV-001", "IMP-001", "IMP-002", "IMP-003"],
        "circular-bom": ["BOM-003"],
        "ambiguous-duplicate": ["ITEM-002", "ITEM-003"],
    }
    for index, (key, case_id, release_type, product, state, severity) in enumerate(SCENARIOS):
        packet = ReleasePacket(
            id=case_id,
            source_id=f"SRC-{case_id}",
            content_hash=digest(key),
            release_type=release_type,
            product=product,
            state=state,
            severity=severity,
            owner_id="user-coordinator",
            version=1,
            approval_status=ApprovalStatus.PENDING if state == CaseState.APPROVAL_PENDING else None,
            scenario_key=key,
            created_at=datetime.now(UTC) - timedelta(hours=8 + index * 6),
        )
        db.add(packet)
        db.flush()
        docs = ["engineering-change-order.md", "cad-bom.csv", "supplier-setup.txt"]
        for name in docs:
            db.add(
                ReleaseDocument(
                    case_id=case_id,
                    filename=name,
                    source_type=name.rsplit(".", 1)[-1].upper(),
                    content_hash=digest([key, name]),
                )
            )
        db.add(
            ExtractionResult(
                case_id=case_id,
                field_name="item_description",
                value=product,
                confidence=0.96,
                evidence={"document": docs[0], "section": "Change summary"},
                model_generated=False,
            )
        )
        for rule_id in scenario_rules[key]:
            explanation = dict(RULES)[rule_id]
            hard_stop = rule_id in {"BOM-003"} or key == "ambiguous-duplicate"
            db.add(
                ValidationFinding(
                    case_id=case_id,
                    rule_id=rule_id,
                    severity=Severity.HARD_STOP if hard_stop else Severity.ERROR,
                    explanation=explanation,
                    affected_record=product,
                    evidence={"document": docs[1], "location": "row 4"},
                    current_value="ERP value",
                    candidate_value="Release packet value",
                    confidence=0.94,
                    suggested_action="Review and stage a bounded correction",
                    approval_required=True,
                )
            )
        impacts = {
            "new-pump": [("BOM", "BOM-001", "New assembly structure differs from ERP", "MEDIUM")],
            "package-change": [
                (
                    "PURCHASE_ORDER",
                    "PO-00008",
                    "Quantity 110 violates MOQ 120 and pack multiple 24",
                    "HIGH",
                ),
                ("PURCHASE_ORDER", "PO-00012", "Quantity 130 violates pack multiple 24", "HIGH"),
            ],
            "obsolete-revision": [
                ("BOM", "BOM-010", "Old seal revision used by pump assembly", "HIGH"),
                ("INVENTORY", "ITEM-0042", "151 units remain on hand", "MEDIUM"),
                ("WORK_ORDER", "WO-00014", "Released work order consumes old seal", "HIGH"),
                ("CUSTOMER_ORDER", "SO-00009", "Commitment may be exposed to delay", "HIGH"),
            ],
            "circular-bom": [
                ("BOM", "BOM-CYCLE", "Path contains parent self-reference", "CRITICAL")
            ],
            "ambiguous-duplicate": [
                ("ITEM", "ITEM-0119", "Candidate one of two plausible existing items", "HIGH")
            ],
        }[key]
        for impact_type, record_id, summary, risk in impacts:
            db.add(
                ImpactRecord(
                    case_id=case_id,
                    impact_type=impact_type,
                    record_id=record_id,
                    summary=summary,
                    risk=risk,
                    graph_path=[product, record_id],
                )
            )
        change_set = ProposedChangeSet(
            id=f"PCS-{case_id}",
            case_id=case_id,
            case_version=1,
            digest=digest([case_id, scenario_rules[key]]),
            status="STAGED",
        )
        db.add(change_set)
        db.add(
            ProposedChange(
                change_set_id=change_set.id,
                action_class="Change package or MOQ data"
                if key == "package-change"
                else "Correct conflicting field",
                entity_type="Item",
                entity_id="ITEM-0220" if key == "package-change" else "ITEM-0001",
                field_name="base_uom",
                before_value=None if key == "new-pump" else "EA",
                after_value="EA",
                evidence={"document": docs[-1]},
            )
        )
        if state == CaseState.APPROVAL_PENDING:
            db.add(
                ApprovalRequest(
                    id=f"APR-{case_id}",
                    case_id=case_id,
                    change_set_id=change_set.id,
                    required_role=Role.APPROVER,
                    token_hash=digest([case_id, "pending"]),
                    case_version=1,
                    status=ApprovalStatus.PENDING,
                )
            )
        if key == "ambiguous-duplicate":
            db.add_all(
                [
                    DuplicateCandidate(
                        case_id=case_id,
                        candidate_item_id="ITEM-0119",
                        score=0.91,
                        reasons=["similar normalized description", "same material"],
                    ),
                    DuplicateCandidate(
                        case_id=case_id,
                        candidate_item_id="ITEM-0120",
                        score=0.89,
                        reasons=["similar normalized description", "same family"],
                    ),
                ]
            )
        db.add(
            AuditEvent(
                id=str(uuid.uuid4()),
                case_id=case_id,
                actor_type="SYSTEM",
                actor_id="fixture-seed",
                service="seed",
                action="scenario_created",
                input_hash=digest(key),
                previous_state=None,
                new_state=state,
                before_values={},
                after_values={"scenario": key},
                evidence_refs=[],
                approval_reference=None,
                result="SUCCESS",
                error_information=None,
                correlation_id=str(uuid.uuid4()),
            )
        )
    db.commit()
    return {
        "items": 300,
        "boms": 45,
        "routings": 20,
        "suppliers": 18,
        "approved_vendors": 40,
        "po_lines": 70,
        "work_orders": 60,
        "inventory_balances": 35,
        "customer_order_lines": 25,
        "engineering_change_orders": 30,
        "release_cases": 5,
    }
