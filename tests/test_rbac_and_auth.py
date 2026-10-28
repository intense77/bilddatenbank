"""
Tests für KDG-konforme rollenbasierte Zugriffskontrolle (RBAC) und Authentifizierung:
- Standard-Benutzer und PBKDF2-Passworthashing
- Login, Logout, Session-Cookies und Bearer-Tokens
- Benutzerverwaltung (CRUD, nur für Administratoren)
- Rollenrechte: Viewer (Lesesaal), Curator (Archivar), Admin (Leitung)
- KDG § 11 Datenschutz: Ausblenden unbestätigter biometrischer Gesichtsdaten (KI_AUTO) im Lesesaal
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.auth import Role, hash_password, verify_password
from app.services.metadata_db import metadata_db
from app.api.deps import get_qdrant_service


def test_password_hashing():
    """Prüft sicheres PBKDF2-Passwort-Hashing mit Salt."""
    pw = "Geheim123!"
    hashed = hash_password(pw)
    assert hashed.startswith("pbkdf2:sha256:100000:")
    assert verify_password(pw, hashed) is True
    assert verify_password("FalschesPasswort", hashed) is False


def test_default_user_seeding():
    """Prüft, dass Standardbenutzer (admin, archivar, lesesaal) in SQLite initialisiert sind."""
    admin_user = metadata_db.get_user_by_username("admin")
    assert admin_user is not None
    assert admin_user["role"] == "admin"
    assert verify_password(settings.AUTH_DEFAULT_ADMIN_PASSWORD, admin_user["password_hash"])

    curator_user = metadata_db.get_user_by_username("archivar")
    assert curator_user is not None
    assert curator_user["role"] == "curator"
    assert verify_password(settings.AUTH_DEFAULT_CURATOR_PASSWORD, curator_user["password_hash"])

    viewer_user = metadata_db.get_user_by_username("lesesaal")
    assert viewer_user is not None
    assert viewer_user["role"] == "viewer"
    assert verify_password(settings.AUTH_DEFAULT_VIEWER_PASSWORD, viewer_user["password_hash"])


def test_login_and_logout_flow():
    """Testet Login (Token + Cookie), Abfrage /api/auth/me und Logout."""
    client = TestClient(app)

    # 1. Fehlgeschlagener Login
    res_fail = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res_fail.status_code == 401

    # 2. Erfolgreicher Login als Archivar (Kurator)
    res_login = client.post("/api/auth/login", json={"username": "archivar", "password": settings.AUTH_DEFAULT_CURATOR_PASSWORD})
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert "token" in login_data
    assert login_data["user"]["role"] == "curator"
    token = login_data["token"]
    assert "session_id" in res_login.cookies

    # 3. GET /api/auth/me mit Bearer Token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "archivar"
    assert res_me.json()["role"] == "curator"

    # 4. GET /api/auth/me mit Session Cookie
    client.cookies.set("session_id", token)
    res_me_cookie = client.get("/api/auth/me")
    assert res_me_cookie.status_code == 200
    assert res_me_cookie.json()["username"] == "archivar"

    # 5. Logout
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200

    # Nach Logout ist die Session ungültig -> Rückfall auf Lesesaal-Gast
    res_after = client.get("/api/auth/me")
    assert res_after.status_code == 200
    assert res_after.json()["role"] == "viewer"


def test_anonymous_lesesaal_viewer_role():
    """Prüft, dass nicht angemeldete Anfragen standardmäßig die Lesesaal-Gastrolle erhalten."""
    client = TestClient(app)
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "viewer"
    assert "Lesesaal" in data["display_name"]


def test_user_management_rbac():
    """Prüft, dass nur Administratoren Benutzer erstellen, auflisten und löschen können."""
    client_viewer = TestClient(app)
    client_admin = TestClient(app)
    client_admin.headers["Authorization"] = "Basic YWRtaW46YXJjaGl2YWRtaW4yMDI2"

    # 1. Lesesaal-Gast darf keine Benutzer auflisten (403)
    res_list_viewer = client_viewer.get("/api/auth/users")
    assert res_list_viewer.status_code == 403

    # 2. Administrator darf Benutzer auflisten (200)
    res_list_admin = client_admin.get("/api/auth/users")
    assert res_list_admin.status_code == 200
    users = res_list_admin.json()
    assert any(u["username"] == "admin" for u in users)

    # 3. Administrator erstellt neuen Benutzer
    new_username = "test_forscher_2026"
    res_create = client_admin.post(
        "/api/auth/users",
        json={
            "username": new_username,
            "password": "SicheresPasswort123!",
            "role": "curator",
            "display_name": "Dr. Forscher",
        },
    )
    assert res_create.status_code == 201
    assert res_create.json()["username"] == new_username

    # 4. Bearbeiten
    res_patch = client_admin.patch(
        f"/api/auth/users/{new_username}",
        json={"display_name": "Prof. Dr. Forscher"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["display_name"] == "Prof. Dr. Forscher"

    # 5. Löschen
    res_del = client_admin.delete(f"/api/auth/users/{new_username}")
    assert res_del.status_code == 200


def test_endpoint_protection_by_roles(tmp_path):
    """
    Testet die Absicherung geschützter Endpunkte nach Rollen:
    - Viewer darf keine Metadaten speichern (403)
    - Curator darf Metadaten speichern (200), aber keine System-Prunes durchführen (403)
    - Admin darf System-Prunes durchführen (200)
    """
    client_viewer = TestClient(app)
    client_curator = TestClient(app)
    client_curator.headers["Authorization"] = "Basic YXJjaGl2YXI6a3VyYXRvcjIwMjY="
    client_admin = TestClient(app)
    client_admin.headers["Authorization"] = "Basic YWRtaW46YXJjaGl2YWRtaW4yMDI2"

    # Testdatei im data-Ordner
    test_img = Path("data/test_rbac_img.jpg")
    test_img.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (100, 100), color="red").save(test_img)

    try:
        # A) Metadaten-Update (/images/metadata):
        # Viewer -> 403 Forbidden
        res_v = client_viewer.post(
            "/images/metadata",
            json={"path": str(test_img.resolve()), "title": "Versuchter Viewer Titel"},
        )
        assert res_v.status_code == 403
        assert "Lesesaal-Modus hat nur Lesezugriff" in res_v.json()["detail"]

        # Curator -> 200 Success
        res_c = client_curator.post(
            "/images/metadata",
            json={"path": str(test_img.resolve()), "title": "Gültiger Kurator Titel"},
        )
        assert res_c.status_code == 200
        assert res_c.json()["status"] == "success"

        # B) System Prune (/api/system/prune):
        # Curator -> 403 Forbidden (erfordert Admin)
        res_prune_c = client_curator.post("/api/system/prune?dry_run=true")
        assert res_prune_c.status_code == 403

        # Admin -> 200 Success
        mock_qdrant = MagicMock()
        mock_qdrant.prune_orphaned_records.return_value = {"scanned": 10, "orphans_deleted": 0}
        app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant
        res_prune_a = client_admin.post("/api/system/prune?dry_run=true")
        assert res_prune_a.status_code == 200
    finally:
        app.dependency_overrides.pop(get_qdrant_service, None)
        test_img.unlink(missing_ok=True)


def test_kdg_section_11_biometrics_filtering_for_viewer(tmp_path):
    """
    Testet § 11 KDG / Art. 9 DSGVO Konformität:
    - Lesesaal-Gäste (Viewer) sehen bei Bilddetails nur verifizierte Gesichter (VERIFIED).
      Unbestätigte KI-Gesichter (KI_AUTO) werden zum Schutz der Betroffenenrechte ausgeblendet.
    - Kuratoren und Administratoren sehen auch unbestätigte Gesichter (KI_AUTO),
      um diese prüfen und kuratieren zu können.
    """
    test_img = Path("data/test_kdg_img.jpg")
    test_img.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (600, 400), color="gray").save(test_img)

    mock_qdrant = MagicMock()
    # 2 Gesichter: Eines KI_AUTO (unbestätigt), eines VERIFIED
    face_unverified = MagicMock()
    face_unverified.id = "face-auto-1"
    face_unverified.payload = {
        "file_path": str(test_img.resolve()),
        "bbox": [50, 50, 150, 150],
        "label": "KI-Vermutung: Pfarrer Huber",
        "curation_status": "KI_AUTO",
    }
    face_verified = MagicMock()
    face_verified.id = "face-verified-2"
    face_verified.payload = {
        "file_path": str(test_img.resolve()),
        "bbox": [250, 50, 350, 150],
        "label": "Bischof Müller",
        "curation_status": "VERIFIED",
    }
    mock_qdrant.client.scroll.side_effect = [
        ([], None),  # archive_images
        ([face_unverified, face_verified], None),  # archive_faces
    ]
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # 1. Lesesaal-Gast (Viewer) ruft Bilddetails ab
        client_viewer = TestClient(app)
        res_v = client_viewer.get(f"/images/details?path={str(test_img.resolve())}")
        assert res_v.status_code == 200
        faces_viewer = res_v.json().get("faces", [])
        # Es darf NUR das verifizierte Gesicht ausgeliefert werden (§ 11 KDG)
        assert len(faces_viewer) == 1
        assert faces_viewer[0]["face_id"] == "face-verified-2"
        assert faces_viewer[0]["curation_status"] == "VERIFIED"

        # 2. Kurator ruft selbe Bilddetails ab
        mock_qdrant.client.scroll.side_effect = [
            ([], None),
            ([face_unverified, face_verified], None),
        ]
        client_curator = TestClient(app)
        client_curator.headers["Authorization"] = "Basic YXJjaGl2YXI6a3VyYXRvcjIwMjY="
        res_c = client_curator.get(f"/images/details?path={str(test_img.resolve())}")
        assert res_c.status_code == 200
        faces_curator = res_c.json().get("faces", [])
        # Kurator sieht BEIDE Gesichter, um die KI-Zuweisung prüfen zu können
        assert len(faces_curator) == 2
        status_list = [f["curation_status"] for f in faces_curator]
        assert "KI_AUTO" in status_list
        assert "VERIFIED" in status_list

    finally:
        app.dependency_overrides.pop(get_qdrant_service, None)
        test_img.unlink(missing_ok=True)
