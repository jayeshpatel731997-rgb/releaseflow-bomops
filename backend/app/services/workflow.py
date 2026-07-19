from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import networkx as nx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.enums import ApprovalStatus, CaseState, Role, Severity
from app.models.entities import (
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    DuplicateCandidate,
    Escalation,
    ImpactRecord,
    Item,
    PostingTransaction,
    ProposedChange,
    ProposedChangeSet,
    ReleasePacket,
    User,
    ValidationFinding,
)

TRANSITIONS: dict[CaseState, set[CaseState]] = {
    CaseState.RECEIVED: {CaseState.INGESTED},
    CaseState.INGESTED: {CaseState.EXTRACTION_COMPLETE},
    CaseState.EXTRACTION_COMPLETE: {CaseState.VALIDATION_IN_PROGRESS},
    CaseState.VALIDATION_IN_PROGRESS: {
        CaseState.VALIDATION_FAILED,
        CaseState.REVIEW_REQUIRED,
        CaseState.READY_FOR_APPROVAL,
    },
    CaseState.REVIEW_REQUIRED: {CaseState.READY_FOR_APPROVAL, CaseState.ESCALATED},
    CaseState.READY_FOR_APPROVAL: {CaseState.APPROVAL_PENDING},
    CaseState.APPROVAL_PENDING: {
        CaseState.APPROVED,
        CaseState.REJECTED,
        CaseState.CHANGES_REQUESTED,
    },
    CaseState.APPROVED: {CaseState.POSTING_IN_PROGRESS},
    CaseState.POSTING_IN_PROGRESS: {CaseState.POSTED, CaseState.ROLLED_BACK},
    CaseState.POSTED: {CaseState.REVALIDATION_IN_PROGRESS},
    CaseState.REVALIDATION_IN_PROGRESS: {CaseState.CLOSED, CaseState.ESCALATED},
}


class WorkflowError(RuntimeError):
    pass


class AuthorizationError(WorkflowError):
    pass


@dataclass(frozen=True)
class DuplicateScore:
    score: float
    reasons: list[str]


def normalized(value: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def duplicate_score(description: str, mpn: str | None, item: Item) -> DuplicateScore:
    reasons: list[str] = []
    description_score = SequenceMatcher(
        None, normalized(description), normalized(item.description)
    ).ratio()
    score = description_score * 0.55
    if description_score >= 0.8:
        reasons.append("similar normalized description")
    if (
        mpn
        and item.manufacturer_part_number
        and normalized(mpn) == normalized(item.manufacturer_part_number)
    ):
        score += 0.45
        reasons.append("exact manufacturer part number")
    return DuplicateScore(round(min(score, 1.0), 3), reasons)


def bom_graph(lines: list[tuple[str, str]]) -> nx.DiGraph[str]:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_edges_from(lines)
    return graph


class ReleaseOrchestrator:
    def __init__(self, db: Session, actor: User, correlation_id: str):
        self.db = db
        self.actor = actor
        self.correlation_id = correlation_id

    def audit(
        self,
        case_id: str | None,
        service: str,
        action: str,
        result: str,
        previous: str | None = None,
        new: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        approval: str | None = None,
        error: str | None = None,
    ) -> None:
        payload = before or {}
        self.db.add(
            AuditEvent(
                id=str(uuid.uuid4()),
                case_id=case_id,
                actor_type="HUMAN",
                actor_id=self.actor.id,
                service=service,
                action=action,
                input_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                previous_state=previous,
                new_state=new,
                before_values=payload,
                after_values=after or {},
                evidence_refs=[],
                approval_reference=approval,
                result=result,
                error_information=error,
                correlation_id=self.correlation_id,
            )
        )

    def transition(self, case: ReleasePacket, new_state: CaseState) -> None:
        old = CaseState(case.state)
        if new_state not in TRANSITIONS.get(old, set()):
            message = f"Invalid transition {old} -> {new_state}"
            self.audit(case.id, "orchestration", "transition", "REJECTED", old, old, error=message)
            raise WorkflowError(message)
        case.state = new_state
        self.audit(case.id, "orchestration", "transition", "SUCCESS", old, new_state)

    def decide(self, approval: ApprovalRequest, decision: str, rationale: str) -> str | None:
        case = self.db.get(ReleasePacket, approval.case_id)
        if not case or approval.status != ApprovalStatus.PENDING:
            raise WorkflowError("Approval is not pending")
        if approval.case_version != case.version:
            raise WorkflowError("Approval is stale because the case version changed")
        if self.actor.role not in {approval.required_role, Role.ADMIN}:
            raise AuthorizationError("User does not hold the required approval role")
        normalized_decision = ApprovalStatus(decision)
        approval.status = normalized_decision
        case.approval_status = normalized_decision
        self.db.add(
            ApprovalDecision(
                approval_request_id=approval.id,
                actor_id=self.actor.id,
                decision=normalized_decision,
                rationale=rationale,
            )
        )
        target = {
            ApprovalStatus.APPROVED: CaseState.APPROVED,
            ApprovalStatus.REJECTED: CaseState.REJECTED,
            ApprovalStatus.CHANGES_REQUESTED: CaseState.CHANGES_REQUESTED,
        }[normalized_decision]
        self.transition(case, target)
        token: str | None = None
        if normalized_decision == ApprovalStatus.APPROVED:
            token = secrets.token_urlsafe(32)
            approval.token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.audit(
            case.id,
            "approvals",
            "decision",
            "SUCCESS",
            approval=approval.id,
            after={"decision": decision, "rationale": rationale},
        )
        self.db.commit()
        return token

    def post(self, case: ReleasePacket, token: str, idempotency_key: str) -> PostingTransaction:
        case_id = case.id
        existing = self.db.scalar(
            select(PostingTransaction).where(PostingTransaction.idempotency_key == idempotency_key)
        )
        if existing:
            return existing
        approval = self.db.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.case_id == case.id,
                ApprovalRequest.status == ApprovalStatus.APPROVED,
            )
        )
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if (
            not approval
            or approval.token_hash != token_hash
            or approval.case_version != case.version
        ):
            self.audit(
                case.id, "posting", "post", "REJECTED", error="Invalid or stale approval token"
            )
            self.db.commit()
            raise AuthorizationError("Valid approval for the current case version is required")
        change_set = self.db.get(ProposedChangeSet, approval.change_set_id)
        changes = list(
            self.db.scalars(
                select(ProposedChange).where(ProposedChange.change_set_id == approval.change_set_id)
            )
        )
        if not change_set:
            raise WorkflowError("Approved change set is missing")
        transaction = PostingTransaction(
            id=str(uuid.uuid4()),
            case_id=case.id,
            idempotency_key=idempotency_key,
            status="IN_PROGRESS",
            before_snapshot={},
            after_snapshot={},
            records_written=0,
        )
        self.db.add(transaction)
        try:
            self.transition(case, CaseState.POSTING_IN_PROGRESS)
            before: dict[str, Any] = {}
            after: dict[str, Any] = {}
            for change in changes:
                if change.entity_type == "Item":
                    item = self.db.get(Item, change.entity_id)
                    if item and hasattr(item, change.field_name):
                        before[f"{item.id}.{change.field_name}"] = getattr(item, change.field_name)
                        setattr(item, change.field_name, change.after_value)
                        after[f"{item.id}.{change.field_name}"] = change.after_value
            transaction.before_snapshot = before
            transaction.after_snapshot = after
            transaction.records_written = len(changes)
            transaction.status = "POSTED"
            change_set.status = "POSTED"
            self.transition(case, CaseState.POSTED)
            self.transition(case, CaseState.REVALIDATION_IN_PROGRESS)
            unresolved = (
                self.db.scalar(
                    select(func.count())
                    .select_from(ValidationFinding)
                    .where(
                        ValidationFinding.case_id == case.id,
                        ValidationFinding.severity == Severity.HARD_STOP,
                        ValidationFinding.resolved.is_(False),
                    )
                )
                or 0
            )
            if unresolved:
                self.transition(case, CaseState.ESCALATED)
                self.db.add(
                    Escalation(
                        id=str(uuid.uuid4()),
                        case_id=case.id,
                        reason="Hard-stop finding remains after posting",
                        assigned_role=Role.COORDINATOR,
                    )
                )
            else:
                self.transition(case, CaseState.CLOSED)
            self.audit(
                case.id,
                "posting",
                "post",
                "SUCCESS",
                approval=approval.id,
                before=before,
                after=after,
            )
            self.db.commit()
            return transaction
        except Exception as exc:
            self.db.rollback()
            recovered_case = self.db.get(ReleasePacket, case_id)
            if recovered_case and CaseState(recovered_case.state) == CaseState.POSTING_IN_PROGRESS:
                recovered_case.state = CaseState.ROLLED_BACK
            failed = PostingTransaction(
                id=str(uuid.uuid4()),
                case_id=case_id,
                idempotency_key=idempotency_key,
                status="ROLLED_BACK",
                before_snapshot={},
                after_snapshot={},
                error=str(exc),
            )
            self.db.add(failed)
            self.audit(case_id, "posting", "post", "FAILED", error=str(exc))
            self.db.commit()
            raise


def clear_case_artifacts(db: Session, case_id: str) -> None:
    for model in (ValidationFinding, DuplicateCandidate, ImpactRecord, Escalation):
        db.execute(delete(model).where(model.case_id == case_id))
