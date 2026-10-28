"""
KDG- und DSGVO-konformes Authentifizierungs- und Rollensystem (RBAC)
für das Historische Bildarchiv-Suchsystem.

Unterstützt drei Schutz- und Berechtigungsstufen:
- ADMIN: Vollzugriff (Ingest, System, Audit-Log, Löschen nach KDG § 19, Benutzerverwaltung)
- CURATOR: Erschließung (Metadaten-Bearbeitung, Gesichts-Kuration, Cluster-Merges, Notizen)
- VIEWER: Lesesaal-Modus (Suche, Betrachtung, Leuchttisch, Export; keine Mutationen;
          automatische Filterung unbestätigter biometrischer Gesichtsdaten nach § 11 KDG).
"""

import os
import hmac
import hashlib
import secrets
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

# Enums & Models
class Role(str, Enum):
    ADMIN = "admin"
    CURATOR = "curator"
    VIEWER = "viewer"


ROLE_HIERARCHY = {
    Role.ADMIN: 3,
    Role.CURATOR: 2,
    Role.VIEWER: 1,
}


class User(BaseModel):
    id: Optional[int] = None
    username: str
    role: Role
    display_name: str
    is_active: bool = True
    created_at: Optional[str] = None
    last_login: Optional[str] = None

    def has_role(self, required_role: Role) -> bool:
        """Prüft, ob der Benutzer mindestens die erforderliche Berechtigungsstufe besitzt."""
        return ROLE_HIERARCHY.get(self.role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: User
    expires_at: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: Role = Role.CURATOR
    display_name: Optional[str] = None


class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[Role] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


# Passwort-Hashing mit Salt (PBKDF2-HMAC-SHA256, Standardbibliothek)
def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Erzeugt einen sicheren PBKDF2-Hash mit zufälligem 16-Byte-Salt."""
    if salt is None:
        salt = os.urandom(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}:{salt.hex()}:{derived.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verifiziert ein Klartext-Passwort gegen den gespeicherten Hash."""
    try:
        parts = hashed.split(":")
        if len(parts) != 5 or parts[0] != "pbkdf2" or parts[1] != "sha256":
            return False
        iterations = int(parts[2])
        salt = bytes.fromhex(parts[3])
        expected_derived = bytes.fromhex(parts[4])
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed, expected_derived)
    except Exception:
        return False


def generate_session_token() -> str:
    """Erzeugt ein kryptographisch sicheres Session-Token."""
    return secrets.token_urlsafe(32)


# FastAPI Security Helpers
http_bearer = HTTPBearer(auto_error=False)
http_basic = HTTPBasic(auto_error=False)


def get_current_user_optional(request: Request) -> Optional[User]:
    """
    Ermittelt den aktuellen Benutzer aus Cookie, Authorization-Header (Bearer oder Basic).
    Gibt None zurück, falls keine gültige Authentifizierung übergeben wurde.
    """
    from app.services.metadata_db import metadata_db

    token = None
    # 1. Session Cookie
    if "session_id" in request.cookies:
        token = request.cookies.get("session_id")

    # 2. Authorization Header (Bearer)
    auth_header = request.headers.get("Authorization")
    if auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header.startswith("Basic "):
            # Basic Auth Support für Skripte & AIS-Konnektoren
            import base64
            try:
                decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
                username, password = decoded.split(":", 1)
                user_dict = metadata_db.get_user_by_username(username)
                if user_dict and user_dict.get("is_active") and verify_password(password, user_dict.get("password_hash", "")):
                    return User(
                        id=user_dict["id"],
                        username=user_dict["username"],
                        role=Role(user_dict["role"]),
                        display_name=user_dict.get("display_name", username),
                        is_active=bool(user_dict.get("is_active", 1)),
                        created_at=user_dict.get("created_at"),
                        last_login=user_dict.get("last_login"),
                    )
            except Exception:
                pass

    if token:
        session = metadata_db.get_session(token)
        if session:
            user_dict = metadata_db.get_user_by_id(session["user_id"])
            if user_dict and user_dict.get("is_active"):
                return User(
                    id=user_dict["id"],
                    username=user_dict["username"],
                    role=Role(user_dict["role"]),
                    display_name=user_dict.get("display_name", user_dict["username"]),
                    is_active=bool(user_dict.get("is_active", 1)),
                    created_at=user_dict.get("created_at"),
                    last_login=user_dict.get("last_login"),
                )

    return None


def get_current_user(request: Request) -> User:
    """
    Gibt den authentifizierten Benutzer zurück.
    Falls nicht authentifiziert und AUTH_LESESAAL_ANONYMOUS=True,
    wird ein anonymer Lesesaal-Gast (Viewer) zurückgegeben.
    Andernfalls wird HTTP 401 geworfen.
    """
    if not settings.AUTH_ENABLED:
        # Falls Auth global deaktiviert ist, fungiert jede Anfrage als Admin
        return User(
            id=1,
            username="admin_open",
            role=Role.ADMIN,
            display_name="Lokaler Administrator",
            is_active=True,
        )

    user = get_current_user_optional(request)
    if user:
        return user

    if settings.AUTH_LESESAAL_ANONYMOUS:
        # Lesesaal-Gastmodus: Nur Lesezugriff, biometrische Filterung aktiv
        return User(
            id=None,
            username="lesesaal_gast",
            role=Role.VIEWER,
            display_name="Lesesaal-Gast (Öffentlich)",
            is_active=True,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentifizierung erforderlich. Bitte melden Sie sich an.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(allowed_roles: List[Role]):
    """
    Erstellt eine FastAPI Dependency, die prüft, ob der angemeldete Nutzer
    eine der erlaubten Rollen besitzt.
    """
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            # Spezifische Meldung bei Lesesaal-Zugriff auf Schreibfunktionen
            if user.role == Role.VIEWER:
                detail = "Zugriff verweigert: Der Lesesaal-Modus hat nur Lesezugriff. Bitte als Archivar oder Administrator anmelden."
            else:
                detail = f"Zugriff verweigert: Erfordert eine der folgenden Rollen: {[r.value for r in allowed_roles]}."
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        return user
    return dependency


# Standard-Dependencies zur bequemen Verwendung in Routern
require_admin = require_role([Role.ADMIN])
require_curator = require_role([Role.ADMIN, Role.CURATOR])
require_viewer = require_role([Role.ADMIN, Role.CURATOR, Role.VIEWER])


def is_viewer_only(user: Optional[User]) -> bool:
    """Prüft, ob der Nutzer nur die Lesesaal-Rolle (Viewer) besitzt (für KDG § 11 Filterung)."""
    if not isinstance(user, User):
        return False
    return user.role == Role.VIEWER
