"""
Authentifizierungs- und Benutzerverwaltungs-Endpunkte (RBAC / KDG § 11).
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from app.core.config import settings
from app.core.auth import (
    User,
    Role,
    LoginRequest,
    LoginResponse,
    UserCreateRequest,
    UserUpdateRequest,
    hash_password,
    verify_password,
    generate_session_token,
    get_current_user,
    require_admin,
    require_curator,
)
from app.services.metadata_db import metadata_db

router = APIRouter(prefix="/auth", tags=["Authentifizierung & Rollen"])


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, response: Response):
    """
    Meldet einen Benutzer mit Benutzername und Passwort an.
    Setzt ein sicheres HttpOnly-Session-Cookie und liefert ein Bearer-Token zurück.
    """
    user_dict = metadata_db.get_user_by_username(credentials.username)
    if not user_dict or not user_dict.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Benutzername oder Passwort.",
        )

    if not verify_password(credentials.password, user_dict.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Benutzername oder Passwort.",
        )

    # Token & Session generieren
    token = generate_session_token()
    expires_at = datetime.now() + timedelta(hours=settings.AUTH_SESSION_EXPIRE_HOURS)
    metadata_db.create_session(token=token, user_id=user_dict["id"], expires_at=expires_at)
    metadata_db.update_user_last_login(user_dict["id"])

    # HttpOnly Cookie setzen
    response.set_cookie(
        key="session_id",
        value=token,
        max_age=settings.AUTH_SESSION_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
    )

    user = User(
        id=user_dict["id"],
        username=user_dict["username"],
        role=Role(user_dict["role"]),
        display_name=user_dict.get("display_name", user_dict["username"]),
        is_active=bool(user_dict.get("is_active", 1)),
        created_at=user_dict.get("created_at"),
        last_login=datetime.now().isoformat(),
    )

    return LoginResponse(
        token=token,
        user=user,
        expires_at=expires_at.isoformat(),
    )


@router.post("/logout")
def logout(request: Request, response: Response):
    """
    Meldet den aktuellen Benutzer ab und invalidiert das Session-Token.
    """
    token = request.cookies.get("session_id")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if token:
        metadata_db.delete_session(token)

    response.delete_cookie(key="session_id")
    return {"status": "success", "message": "Erfolgreich abgemeldet."}


@router.get("/me", response_model=User)
def get_current_user_profile(user: User = Depends(get_current_user)):
    """
    Liefert das Profil und die Rolle des aktuell angemeldeten Benutzers
    (bzw. den Lesesaal-Gaststatus).
    """
    return user


@router.get("/users", response_model=List[User])
def list_users(admin: User = Depends(require_admin)):
    """
    Listet alle registrierten Benutzer auf (nur für Administratoren).
    """
    rows = metadata_db.list_users()
    return [
        User(
            id=r["id"],
            username=r["username"],
            role=Role(r["role"]),
            display_name=r.get("display_name", r["username"]),
            is_active=bool(r.get("is_active", 1)),
            created_at=r.get("created_at"),
            last_login=r.get("last_login"),
        )
        for r in rows
    ]


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreateRequest, admin: User = Depends(require_admin)):
    """
    Erstellt ein neues Benutzerkonto (nur für Administratoren).
    """
    existing = metadata_db.get_user_by_username(data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Benutzername '{data.username}' existiert bereits.",
        )

    pw_hash = hash_password(data.password)
    user_id = metadata_db.create_user(
        username=data.username,
        password_hash=pw_hash,
        role=data.role.value,
        display_name=data.display_name or data.username,
    )

    metadata_db.add_audit_log(
        action="CREATE_USER",
        target_type="USER",
        target_id=data.username,
        details={"role": data.role.value, "display_name": data.display_name},
        operator=admin.username,
    )

    created = metadata_db.get_user_by_id(user_id)
    return User(
        id=created["id"],
        username=created["username"],
        role=Role(created["role"]),
        display_name=created["display_name"],
        is_active=bool(created["is_active"]),
        created_at=created["created_at"],
    )


@router.patch("/users/{username}", response_model=User)
def update_user(
    username: str,
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Aktualisiert Benutzerdaten.
    Administratoren dürfen alle Benutzer bearbeiten.
    Reguläre Benutzer dürfen nur ihr eigenes Passwort und ihren Anzeigenamen ändern.
    """
    target = metadata_db.get_user_by_username(username)
    if not target:
        raise HTTPException(status_code=404, detail=f"Benutzer '{username}' nicht gefunden.")

    is_self = current_user.username == username
    is_admin = current_user.role == Role.ADMIN

    if not is_admin and not is_self:
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Bearbeiten fremder Benutzer.")

    pw_hash = hash_password(data.password) if data.password else None
    role = data.role.value if (data.role and is_admin) else None
    is_active = data.is_active if is_admin else None

    # Falls regulärer Nutzer versucht Rolle oder Aktivitätsstatus zu ändern:
    if not is_admin and (data.role is not None or data.is_active is not None):
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen Rollen oder Sperrstatus ändern.")

    metadata_db.update_user(
        user_id=target["id"],
        password_hash=pw_hash,
        role=role,
        display_name=data.display_name,
        is_active=is_active,
    )

    metadata_db.add_audit_log(
        action="UPDATE_USER",
        target_type="USER",
        target_id=username,
        details={"is_self": is_self, "role_changed": role is not None},
        operator=current_user.username,
    )

    updated = metadata_db.get_user_by_id(target["id"])
    return User(
        id=updated["id"],
        username=updated["username"],
        role=Role(updated["role"]),
        display_name=updated["display_name"],
        is_active=bool(updated["is_active"]),
        created_at=updated["created_at"],
        last_login=updated["last_login"],
    )


@router.delete("/users/{username}")
def delete_user(username: str, admin: User = Depends(require_admin)):
    """
    Löscht ein Benutzerkonto (nur für Administratoren).
    Der eigene Administrator-Account kann nicht gelöscht werden.
    """
    if username == admin.username:
        raise HTTPException(status_code=400, detail="Der eigene Administrator-Account kann nicht gelöscht werden.")

    target = metadata_db.get_user_by_username(username)
    if not target:
        raise HTTPException(status_code=404, detail=f"Benutzer '{username}' nicht gefunden.")

    metadata_db.delete_user(username)
    metadata_db.add_audit_log(
        action="DELETE_USER",
        target_type="USER",
        target_id=username,
        details={},
        operator=admin.username,
    )

    return {"status": "success", "message": f"Benutzer '{username}' gelöscht."}
