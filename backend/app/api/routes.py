from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.db.seed import SCENARIOS, seed_database
from app.db.session import get_db
from app.models.entities import (
    ApprovalRequest,
    AuditEvent,
    DuplicateCandidate,
    Escalation,
    ExtractionResult,
    ImpactRecord,
    PostingTransaction,
    ProposedChange,
    ProposedChangeSet,
    ReleaseDocument,
    ReleasePacket,
    User,
    ValidationFinding,
)
from app.schemas.api import CaseSummary, DecisionInput, Page, PostInput, ReplayInput
from app.services.workflow import AuthorizationError, ReleaseOrchestrator, WorkflowError

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(get_db)]


def actor(
    db: DB, user_id: Annotated[str, Header(alias="X-Demo-User-ID")] = "user-coordinator"
) -> User:
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(403, "Unknown or inactive demo user")
    return user


Actor = Annotated[User, Depends(actor)]


def record_dict(record: Any) -> dict[str, Any]:
    return {
        attribute.key: getattr(record, attribute.key)
        for attribute in inspect(record).mapper.column_attrs
    }


@router.get("/health")
def health(db: DB) -> dict[str, str]:
    db.scalar(select(func.count()).select_from(ReleasePacket))
    return {"status": "healthy", "service": "releaseflow-api", "mode": "deterministic-fixture"}


@router.post("/demo/seed")
def seed(db: DB) -> dict[str, Any]:
    return {"status": "seeded", "counts": seed_database(db)}


@router.post("/demo/reset")
def reset(db: DB) -> dict[str, Any]:
    return {"status": "reset", "counts": seed_database(db)}


@router.post("/demo/replay")
def replay(payload: ReplayInput, db: DB) -> dict[str, str]:
    valid = {scenario[0]: scenario[1] for scenario in SCENARIOS}
    if payload.scenario_key not in valid:
        raise HTTPException(404, "Unknown scenario")
    seed_database(db)
    return {"status": "replayed", "case_id": valid[payload.scenario_key]}


@router.get("/users")
def users(db: DB) -> list[dict[str, Any]]:
    return [
        {"id": u.id, "name": u.name, "role": u.role}
        for u in db.scalars(select(User).order_by(User.name))
    ]


@router.get("/cases", response_model=Page[CaseSummary])
def cases(
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    state: str | None = None,
    severity: str | None = None,
    release_type: str | None = None,
    owner: str | None = None,
    sort: str = "created_at",
    direction: str = "desc",
) -> Page[CaseSummary]:
    query = select(ReleasePacket)
    for column, value in (
        (ReleasePacket.state, state),
        (ReleasePacket.severity, severity),
        (ReleasePacket.release_type, release_type),
        (ReleasePacket.owner_id, owner),
    ):
        if value:
            query = query.where(column == value)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    sort_column = {
        "created_at": ReleasePacket.created_at,
        "severity": ReleasePacket.severity,
        "state": ReleasePacket.state,
    }.get(sort, ReleasePacket.created_at)
    query = query.order_by(sort_column.asc() if direction == "asc" else sort_column.desc())
    records = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    items = []
    for record in records:
        count = (
            db.scalar(
                select(func.count())
                .select_from(ValidationFinding)
                .where(ValidationFinding.case_id == record.id)
            )
            or 0
        )
        data = CaseSummary.model_validate(record)
        data.finding_count = count
        items.append(data)
    return Page(items=items, page=page, page_size=page_size, total=total)


def case_or_404(db: Session, case_id: str) -> ReleasePacket:
    case = db.get(ReleasePacket, case_id)
    if not case:
        raise HTTPException(404, "Release case not found")
    return case


@router.get("/cases/{case_id}")
def case_detail(case_id: str, db: DB) -> dict[str, Any]:
    case = case_or_404(db, case_id)

    def rows(model: Any) -> list[Any]:
        return list(db.scalars(select(model).where(model.case_id == case_id)))

    change_sets = rows(ProposedChangeSet)
    changes = (
        list(
            db.scalars(
                select(ProposedChange).where(
                    ProposedChange.change_set_id.in_([c.id for c in change_sets])
                )
            )
        )
        if change_sets
        else []
    )
    return {
        "case": CaseSummary.model_validate(case),
        "documents": [record_dict(row) for row in rows(ReleaseDocument)],
        "extractions": [record_dict(row) for row in rows(ExtractionResult)],
        "findings": [record_dict(row) for row in rows(ValidationFinding)],
        "duplicates": [record_dict(row) for row in rows(DuplicateCandidate)],
        "impacts": [record_dict(row) for row in rows(ImpactRecord)],
        "change_sets": [record_dict(row) for row in change_sets],
        "changes": [record_dict(row) for row in changes],
        "approvals": [record_dict(row) for row in rows(ApprovalRequest)],
        "postings": [record_dict(row) for row in rows(PostingTransaction)],
        "escalations": [record_dict(row) for row in rows(Escalation)],
    }


@router.get("/cases/{case_id}/documents")
def documents(case_id: str, db: DB) -> list[Any]:
    case_or_404(db, case_id)
    return [
        record_dict(row)
        for row in db.scalars(select(ReleaseDocument).where(ReleaseDocument.case_id == case_id))
    ]


@router.get("/cases/{case_id}/findings")
def findings(case_id: str, db: DB) -> list[Any]:
    return [
        record_dict(row)
        for row in db.scalars(select(ValidationFinding).where(ValidationFinding.case_id == case_id))
    ]


@router.get("/cases/{case_id}/duplicates")
def duplicates(case_id: str, db: DB) -> list[Any]:
    return [
        record_dict(row)
        for row in db.scalars(
            select(DuplicateCandidate).where(DuplicateCandidate.case_id == case_id)
        )
    ]


@router.get("/cases/{case_id}/impacts")
def impacts(case_id: str, db: DB) -> list[Any]:
    return [
        record_dict(row)
        for row in db.scalars(select(ImpactRecord).where(ImpactRecord.case_id == case_id))
    ]


@router.get("/approvals")
def approvals(db: DB) -> list[Any]:
    return [
        record_dict(row)
        for row in db.scalars(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()))
    ]


@router.post("/approvals/{approval_id}/decisions")
def approval_decision(
    approval_id: str, payload: DecisionInput, request: Request, db: DB, user: Actor
) -> dict[str, Any]:
    approval = db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(404, "Approval request not found")
    try:
        token = ReleaseOrchestrator(db, user, request.state.correlation_id).decide(
            approval, payload.decision, payload.rationale
        )
    except AuthorizationError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (WorkflowError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": approval.status, "approval_token": token}


@router.post("/cases/{case_id}/post")
def post(case_id: str, payload: PostInput, request: Request, db: DB, user: Actor) -> Any:
    case = case_or_404(db, case_id)
    try:
        return record_dict(
            ReleaseOrchestrator(db, user, request.state.correlation_id).post(
                case, payload.approval_token, payload.idempotency_key
            )
        )
    except AuthorizationError as exc:
        raise HTTPException(403, str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/cases/{case_id}/revalidate")
def revalidate(case_id: str, db: DB) -> dict[str, Any]:
    case = case_or_404(db, case_id)
    unresolved = (
        db.scalar(
            select(func.count())
            .select_from(ValidationFinding)
            .where(ValidationFinding.case_id == case_id, ValidationFinding.resolved.is_(False))
        )
        or 0
    )
    return {"case_id": case.id, "state": case.state, "unresolved_findings": unresolved}


@router.get("/escalations")
def escalations(db: DB) -> list[Any]:
    return [
        record_dict(row)
        for row in db.scalars(select(Escalation).order_by(Escalation.created_at.desc()))
    ]


@router.get("/cases/{case_id}/audit")
def audit(case_id: str, db: DB) -> list[Any]:
    return [
        record_dict(row)
        for row in db.scalars(
            select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.timestamp)
        )
    ]


@router.get("/kpis")
def kpis(db: DB) -> dict[str, Any]:
    case_count = db.scalar(select(func.count()).select_from(ReleasePacket)) or 0
    finding_count = db.scalar(select(func.count()).select_from(ValidationFinding)) or 0
    escalated = (
        db.scalar(
            select(func.count())
            .select_from(ReleasePacket)
            .where(ReleasePacket.state == "ESCALATED")
        )
        or 0
    )
    return {
        "primary_metric": "Median release packet to approved ERP-ready posting",
        "median_release_cycle_hours": 14.2,
        "manual_touches_per_case": 2.4,
        "findings_detected_before_posting": finding_count,
        "escalation_rate": round(escalated / case_count, 2) if case_count else 0,
        "first_pass_revalidation_rate": 0.8,
        "blocked_posting_attempts": 3,
    }
