import pytest


@pytest.mark.parametrize("role,method,path,body,code", [
    (None, "GET", "/api/projects", None, 401),
    ("viewer", "GET", "/api/projects", None, 200),
    ("viewer", "POST", "/api/projects", {"name": "x", "industry": "gtl", "stage": "FEED"}, 403),
    ("engineer", "POST", "/api/projects", {"name": "x", "industry": "gtl", "stage": "FEED"}, 201),
    ("engineer", "PATCH", "/api/rules/R001", {"enabled": False}, 403),
    ("lead", "PATCH", "/api/rules/R001", {"enabled": False}, 200),
    ("lead", "GET", "/api/users", None, 403),
    ("engineer", "GET", "/api/audit", None, 403),
    ("admin", "GET", "/api/users", None, 200),
    ("admin", "GET", "/api/audit/verify", None, 200),
])
def test_permissions(client, client_as, role, method, path, body, code):
    c = client_as(role) if role else client
    assert c.request(method, path, json=body).status_code == code


def test_viewer_cannot_upload_review_or_decide(client_as, reviewed, sample_docs, upload):
    _, pid = reviewed
    v = client_as("viewer")
    fid = v.get(f"/api/projects/{pid}/findings").json()[0]["id"]
    assert v.post(f"/api/projects/{pid}/reviews").status_code == 403
    assert v.post(f"/api/findings/{fid}/actions", json={"action": "confirm", "comment": ""}).status_code == 403
    assert upload(v, pid, sample_docs[0]).status_code == 403
    assert v.get(f"/api/findings/{fid}").status_code == 200


def test_only_lead_and_admin_delete_project(client_as, reviewed):
    c, pid = reviewed
    assert c.delete(f"/api/projects/{pid}").status_code == 403
    assert client_as("lead").delete(f"/api/projects/{pid}").status_code == 204
    assert c.get(f"/api/projects/{pid}").status_code == 404
