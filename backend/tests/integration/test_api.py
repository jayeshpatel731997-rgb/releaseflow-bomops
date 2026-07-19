import pytest


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "healthy"


def test_queue_returns_five_scenarios(client):
    response = client.get("/api/v1/cases")
    assert response.status_code == 200
    assert response.json()["total"] == 5


@pytest.mark.parametrize("case_id", ["CASE-001", "CASE-002", "CASE-003", "CASE-004", "CASE-005"])
def test_case_detail_contains_governance_artifacts(client, case_id):
    data = client.get(f"/api/v1/cases/{case_id}").json()
    assert data["documents"]
    assert data["findings"]
    assert data["impacts"]


def test_unauthorized_posting_is_rejected(client):
    response = client.post(
        "/api/v1/cases/CASE-001/post",
        json={"approval_token": "invalid", "idempotency_key": "post-test-001"},
    )
    assert response.status_code == 403


def test_filter_hard_stops(client):
    data = client.get("/api/v1/cases?severity=HARD_STOP").json()
    assert data["total"] == 2


def test_replay_is_deterministic(client):
    assert (
        client.post("/api/v1/demo/replay", json={"scenario_key": "circular-bom"}).json()["case_id"]
        == "CASE-004"
    )
