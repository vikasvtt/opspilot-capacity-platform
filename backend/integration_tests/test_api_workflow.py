from sqlalchemy import select

from app.models.entities import Approval, ApprovalStatus, CapacityRequest, RequestStatus, Server, UserRole
from conftest import make_site_and_rack, make_user


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_registration_creates_viewer_and_duplicate_is_rejected(client):
    first = client.post("/auth/register", json={"email": "reader@example.test", "password": "StrongPass123!"})
    assert first.status_code == 201
    assert first.json()["role"] == "viewer"
    duplicate = client.post("/auth/register", json={"email": "reader@example.test", "password": "StrongPass123!"})
    assert duplicate.status_code == 409


def test_login_and_refresh_return_valid_token_pairs(client, db):
    user, _ = make_user(db, UserRole.ENGINEER)
    login = client.post("/auth/login", json={"email": user.email, "password": "StrongPass123!"})
    assert login.status_code == 200
    assert client.get("/auth/me", headers=auth(login.json())).json()["role"] == "engineer"
    refreshed = client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refreshed.status_code == 200


def test_viewer_can_read_but_cannot_change_inventory(client, db):
    _viewer, tokens = make_user(db, UserRole.VIEWER)
    assert client.get("/sites", headers=auth(tokens)).status_code == 200
    denied = client.post("/sites", headers=auth(tokens), json={"name": "New", "city": "Pune", "total_capacity": 5})
    assert denied.status_code == 403


def test_agent_proposal_does_not_change_inventory_until_approved(client, db):
    engineer, engineer_tokens = make_user(db, UserRole.ENGINEER)
    _approver, approver_tokens = make_user(db, UserRole.APPROVER)
    site, rack = make_site_and_rack(db, 6)
    request = CapacityRequest(requested_by=engineer.id, site_id=site.id, quantity=4, description="New workload", status=RequestStatus.PENDING)
    db.add(request)
    db.commit()
    db.refresh(request)

    proposal = client.post(f"/agent/requests/{request.id}/propose", headers=auth(engineer_tokens))
    assert proposal.status_code == 201
    db.refresh(rack)
    assert rack.used_slots == 0
    assert db.scalar(select(Server).where(Server.rack_id == rack.id)) is None

    approved = client.post(f"/approvals/{proposal.json()['id']}/review", headers=auth(approver_tokens), json={"decision": "approve", "reason": "Capacity reviewed"})
    assert approved.status_code == 200
    db.refresh(rack)
    db.refresh(request)
    assert rack.used_slots == 4
    assert request.status == RequestStatus.APPROVED
    assert len(list(db.scalars(select(Server).where(Server.rack_id == rack.id)))) == 4
    assert approved.json()["status"] == ApprovalStatus.APPROVED.value


def test_rejected_proposal_leaves_capacity_unchanged(client, db):
    engineer, engineer_tokens = make_user(db, UserRole.ENGINEER)
    _, approver_tokens = make_user(db, UserRole.APPROVER)
    site, rack = make_site_and_rack(db, 8)
    request = CapacityRequest(requested_by=engineer.id, site_id=site.id, quantity=3, description="Test", status=RequestStatus.PENDING)
    db.add(request)
    db.commit()
    db.refresh(request)
    proposal = client.post(f"/agent/requests/{request.id}/propose", headers=auth(engineer_tokens)).json()
    response = client.post(f"/approvals/{proposal['id']}/review", headers=auth(approver_tokens), json={"decision": "reject", "reason": "Not needed"})
    assert response.status_code == 200
    db.refresh(rack)
    db.refresh(request)
    assert rack.used_slots == 0
    assert request.status == RequestStatus.REJECTED
    assert db.scalar(select(Server).where(Server.rack_id == rack.id)) is None


def test_viewer_cannot_review_proposals(client, db):
    _viewer, viewer_tokens = make_user(db, UserRole.VIEWER)
    engineer, engineer_tokens = make_user(db, UserRole.ENGINEER)
    site, _ = make_site_and_rack(db, 5)
    request = CapacityRequest(requested_by=engineer.id, site_id=site.id, quantity=1, description="", status=RequestStatus.PENDING)
    db.add(request)
    db.commit()
    db.refresh(request)
    proposal = client.post(f"/agent/requests/{request.id}/propose", headers=auth(engineer_tokens)).json()
    response = client.post(f"/approvals/{proposal['id']}/review", headers=auth(viewer_tokens), json={"decision": "approve", "reason": "No"})
    assert response.status_code == 403


def test_insufficient_capacity_cannot_create_proposal(client, db):
    engineer, tokens = make_user(db, UserRole.ENGINEER)
    site, _ = make_site_and_rack(db, 2)
    request = CapacityRequest(requested_by=engineer.id, site_id=site.id, quantity=4, description="", status=RequestStatus.PENDING)
    db.add(request)
    db.commit()
    db.refresh(request)
    response = client.post(f"/agent/requests/{request.id}/propose", headers=auth(tokens))
    assert response.status_code == 409
    assert db.scalar(select(Approval).where(Approval.request_id == request.id)) is None


def test_inventory_crud_records_audit_events(client, db):
    _engineer, engineer_tokens = make_user(db, UserRole.ENGINEER)
    _approver, approver_tokens = make_user(db, UserRole.APPROVER)

    site = client.post("/sites", headers=auth(engineer_tokens), json={"name": "Pune DC", "city": "Pune", "total_capacity": 20})
    assert site.status_code == 201
    site_id = site.json()["id"]
    rack = client.post("/racks", headers=auth(engineer_tokens), json={"site_id": site_id, "name": "R-02", "total_slots": 10})
    assert rack.status_code == 201
    rack_id = rack.json()["id"]
    server = client.post("/servers", headers=auth(engineer_tokens), json={"rack_id": rack_id, "hostname": "pune-01"})
    assert server.status_code == 201
    server_id = server.json()["id"]

    assert client.patch(f"/servers/{server_id}", headers=auth(engineer_tokens), json={"status": "maintenance"}).status_code == 200
    assert client.patch(f"/racks/{rack_id}", headers=auth(engineer_tokens), json={"total_slots": 12}).status_code == 200
    assert client.patch(f"/sites/{site_id}", headers=auth(engineer_tokens), json={"city": "Pune City"}).status_code == 200
    assert client.delete(f"/servers/{server_id}", headers=auth(engineer_tokens)).status_code == 204
    assert client.delete(f"/racks/{rack_id}", headers=auth(engineer_tokens)).status_code == 204
    assert client.delete(f"/sites/{site_id}", headers=auth(engineer_tokens)).status_code == 204

    audit = client.get("/audit", headers=auth(approver_tokens))
    assert audit.status_code == 200
    assert len(audit.json()) >= 7


def test_capacity_request_create_update_delete(client, db):
    engineer, tokens = make_user(db, UserRole.ENGINEER)
    site, _ = make_site_and_rack(db)
    created = client.post("/requests", headers=auth(tokens), json={"site_id": site.id, "quantity": 2, "description": "Initial"})
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert created.json()["requested_by"] == engineer.id
    updated = client.patch(f"/requests/{item_id}", headers=auth(tokens), json={"quantity": 3, "description": "Updated"})
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 3
    assert client.get(f"/requests/{item_id}", headers=auth(tokens)).status_code == 200
    assert client.delete(f"/requests/{item_id}", headers=auth(tokens)).status_code == 204
    assert client.get(f"/requests/{item_id}", headers=auth(tokens)).status_code == 404


def test_capacity_reports_agent_read_tools_and_metrics(client, db):
    _engineer, tokens = make_user(db, UserRole.ENGINEER)
    site, rack = make_site_and_rack(db, 10)
    rack.used_slots = 4
    db.commit()

    capacity = client.get(f"/agent/capacity/{site.id}", headers=auth(tokens))
    assert capacity.json()["available_slots"] == 6
    assert client.get("/agent/pending", headers=auth(tokens)).status_code == 200
    report = client.get("/reports/site-utilization", headers=auth(tokens))
    assert report.status_code == 200
    assert report.json()[0]["usage_rank"] == 1
    assert report.json()[0]["utilization_percent"] == 40.0
    assert "opspilot_http_requests_total" in client.get("/metrics").text
    health = client.get("/health")
    assert health.status_code == 200
    assert health.headers.get("x-request-id")


def test_invalid_login_and_unauthenticated_access_are_rejected(client, db):
    user, _ = make_user(db, UserRole.ENGINEER)
    bad_login = client.post("/auth/login", json={"email": user.email, "password": "wrong"})
    assert bad_login.status_code == 401
    assert client.get("/sites").status_code == 401


def test_failed_agent_call_is_audited(client, db):
    engineer, tokens = make_user(db, UserRole.ENGINEER)
    site, _ = make_site_and_rack(db, 1)
    request = CapacityRequest(requested_by=engineer.id, site_id=site.id, quantity=2, description="No room", status=RequestStatus.PENDING)
    db.add(request)
    db.commit()
    db.refresh(request)

    response = client.post(f"/agent/requests/{request.id}/propose", headers=auth(tokens))
    assert response.status_code == 409
    from app.models.entities import AuditLog

    logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "agent.call_failed")))
    assert len(logs) == 1
