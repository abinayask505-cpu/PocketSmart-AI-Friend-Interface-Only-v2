import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
DATA_DIR.mkdir(exist_ok=True)


def _load_users():
    if not USERS_FILE.exists():
        return []
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 120_000
    ).hex()


def register_user(name: str, email: str, password: str):
    users = _load_users()
    if any(u["email"] == email for u in users):
        return False, "An account with this email already exists."
    if len(password) < 6:
        return False, "Password must contain at least 6 characters."

    salt = secrets.token_hex(16)
    users.append({
        "id": secrets.token_hex(8),
        "name": name,
        "email": email,
        "salt": salt,
        "password_hash": _hash(password, salt),
    })
    _save_users(users)
    return True, "Registered successfully."


def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(email)
    if not user:
        return None
    if _hash(password, user["salt"]) != user["password_hash"]:
        return None
    return user


def get_user_by_email(email: str | None):
    if not email:
        return None
    return next((u for u in _load_users() if u["email"] == email), None)


def user_public(user):
    if not user:
        return None
    return {"id": user["id"], "name": user["name"], "email": user["email"]}
