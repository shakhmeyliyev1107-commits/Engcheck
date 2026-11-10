def test_setup_then_login_then_me(client):
    assert client.get("/api/setup").json() == {"needs_setup": True}
    r = client.post("/api/setup", json={"login": "admin", "password": "S3cret-pass"})
    assert r.status_code == 201
    assert client.get("/api/setup").json() == {"needs_setup": False}
    token = client.post("/api/auth/login", json={"login": "admin", "password": "S3cret-pass"}).json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["login"] == "admin" and me["role"] == "admin" and "manage_users" in me["permissions"]
    assert "password_hash" not in me


def test_setup_closed_after_first_admin(client):
    client.post("/api/setup", json={"login": "admin", "password": "S3cret-pass"})
    r = client.post("/api/setup", json={"login": "evil", "password": "S3cret-pass"})
    assert r.status_code == 409 and r.json()["code"] == "setup_done"


def test_setup_rejects_short_password(client):
    r = client.post("/api/setup", json={"login": "admin", "password": "123"})
    assert r.status_code == 422 and r.json()["code"] == "password_too_short"
    assert client.get("/api/setup").json() == {"needs_setup": True}


def test_wrong_password_401(client):
    client.post("/api/setup", json={"login": "admin", "password": "S3cret-pass"})
    r = client.post("/api/auth/login", json={"login": "admin", "password": "nope-nope"})
    assert r.status_code == 401 and r.json()["code"] == "bad_credentials"


def test_logout_invalidates_token(client_as):
    c = client_as("engineer")
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401


def test_error_message_localized(client):
    uz = client.get("/api/projects").json()
    ru = client.get("/api/projects", headers={"Accept-Language": "ru-RU,ru;q=0.9"}).json()
    en = client.get("/api/projects", headers={"Accept-Language": "en"}).json()
    assert uz["code"] == ru["code"] == en["code"] == "unauthorized"
    assert len({uz["message"], ru["message"], en["message"]}) == 3
    assert en["message"] == "Sign in to continue"


def test_user_locale_wins_over_header(client_as):
    c = client_as("viewer")
    assert c.patch("/api/auth/me", json={"locale": "ru"}).json()["locale"] == "ru"
    r = c.post("/api/projects", json={"name": "x", "industry": "gtl", "stage": "FEED"},
               headers={"Accept-Language": "en"})
    assert r.status_code == 403 and r.json()["message"] == "Недостаточно прав для этого действия"


def test_admin_manages_users(client_as):
    a = client_as("admin")
    r = a.post("/api/users", json={"login": "nodira", "password": "S3cret-pass", "role": "lead"})
    assert r.status_code == 201 and r.json()["role"] == "lead"
    uid = r.json()["id"]
    assert a.post("/api/users", json={"login": "nodira", "password": "S3cret-pass", "role": "lead"}).json()["code"] == "login_taken"
    assert a.patch(f"/api/users/{uid}", json={"role": "viewer", "is_active": False}).json()["is_active"] is False
    assert {u["login"] for u in a.get("/api/users").json()} == {"admin", "nodira"}
    actions = [x["action"] for x in a.get("/api/audit").json()]
    assert "user.create" in actions and "user.update" in actions


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["code"] == "not_found"
