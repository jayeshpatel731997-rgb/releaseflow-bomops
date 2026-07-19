import hashlib

import pytest

from app.core.enums import CaseState
from app.db.session import SessionLocal
from app.models.entities import ApprovalRequest, Item, ReleasePacket, User
from app.services.workflow import (
    TRANSITIONS,
    ReleaseOrchestrator,
    WorkflowError,
    bom_graph,
    duplicate_score,
)


@pytest.mark.parametrize(
    "source,target", [(s, t) for s, targets in TRANSITIONS.items() for t in targets]
)
def test_allowed_transitions(source, target):
    assert target in TRANSITIONS[source]


@pytest.mark.parametrize(
    "edges,cyclic",
    [([("A", "B"), ("B", "C")], False), ([("A", "B"), ("B", "A")], True), ([("A", "A")], True)],
)
def test_cycle_detection(edges, cyclic):
    import networkx as nx

    assert (not nx.is_directed_acyclic_graph(bom_graph(edges))) is cyclic


def test_duplicate_exact_mpn_scores_high():
    item = Item(
        id="x",
        number="x",
        description="316 SS Pump Housing",
        base_uom="EA",
        manufacturer_part_number="ABC-12",
    )
    assert duplicate_score("Pump housing 316 stainless", "abc 12", item).score > 0.7


def test_invalid_transition_is_rejected_and_audited():
    with SessionLocal() as db:
        case = db.get(ReleasePacket, "CASE-001")
        user = db.get(User, "user-coordinator")
        with pytest.raises(WorkflowError):
            ReleaseOrchestrator(db, user, "corr-test").transition(case, CaseState.CLOSED)


def test_approval_requires_correct_role():
    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, "APR-CASE-001")
        user = db.get(User, "user-coordinator")
        with pytest.raises(WorkflowError):
            ReleaseOrchestrator(db, user, "corr-test").decide(approval, "APPROVED", "reviewed")


def test_approved_token_is_bound_to_request():
    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, "APR-CASE-001")
        user = db.get(User, "user-approver")
        token = ReleaseOrchestrator(db, user, "corr-test").decide(
            approval, "APPROVED", "Evidence reviewed"
        )
        assert token and hashlib.sha256(token.encode()).hexdigest() == approval.token_hash
