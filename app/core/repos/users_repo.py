# app/core/repos/users_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, delete, update
from passlib.hash import bcrypt, pbkdf2_sha256

from core.db import get_session
from core.models import User

ADMIN_EMAIL = "az.analytics.pro@gmail.com"

# --- helpers hash ---
def _hash_password(raw: str) -> str:
    # Nouveau standard: PBKDF2 (aucune limite 72o)
    return pbkdf2_sha256.hash(raw)

def _is_bcrypt(hash_: str) -> bool:
    return hash_.startswith("$2a$") or hash_.startswith("$2b$") or hash_.startswith("$2y$")

def _verify_and_migrate_if_needed(user: User, raw_password: str, hash_: str, session) -> bool:
    """
    Vérifie hash (bcrypt ou pbkdf2). Si bcrypt ok -> réécrit en PBKDF2 immédiatement.
    """
    if _is_bcrypt(hash_):
        # bcrypt a une limite 72 octets -> si trop long, on sait que ça échouera de toute façon
        if len(raw_password.encode("utf-8")) > 72:
            return False
        ok = bcrypt.verify(raw_password, hash_)
        if ok:
            # migration silencieuse vers PBKDF2
            user.password_hash = _hash_password(raw_password)
            session.add(user)
            session.commit()
        return ok
    else:
        # PBKDF2 par défaut
        return pbkdf2_sha256.verify(raw_password, hash_)


# ----- Lecture -----

def get_user_by_email(email: str) -> Optional[User]:
    email = email.strip().lower()
    with get_session() as s:
        return s.scalars(select(User).where(User.email == email)).first()

def get_user_by_id(user_id: int) -> Optional[User]:
    with get_session() as s:
        return s.get(User, user_id)

def list_users() -> List[Dict[str, Any]]:
    """
    Retourne la liste des utilisateurs (dicts) pour affichage.
    """
    with get_session() as s:
        rows = s.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())).all()
        out = []
        for u in rows:
            out.append({
                "id": u.id,
                "email": u.email,
                "team_name": u.team_name,
                "is_admin": bool(u.is_admin),
                "created_at": u.created_at,
            })
        return out

# ----- Création -----

def create_user(email: str, raw_password: str, team_name: Optional[str] = None, is_admin: bool = False) -> int:
    email = email.strip().lower()
    # admin unique
    if email != ADMIN_EMAIL:
        is_admin = False
    if get_user_by_email(email):
        raise ValueError("Email déjà utilisé.")
    pwd_hash = _hash_password(raw_password)
    u = User(email=email, password_hash=pwd_hash, team_name=team_name, is_admin=is_admin)
    with get_session() as s:
        s.add(u); s.flush(); uid = u.id; s.commit(); return uid
# ----- Mise à jour -----

def verify_password(user: User, raw_password: str) -> bool:
    return bcrypt.verify(raw_password, user.password_hash)

def set_password(email: str, new_raw_password: str) -> bool:
    email = email.strip().lower()
    with get_session() as s:
        u = s.scalars(select(User).where(User.email == email)).first()
        if not u:
            return False
        u.password_hash = _hash_password(new_raw_password)
        s.add(u); s.commit()
        return True

def update_user_team(email: str, team_name: Optional[str]) -> bool:
    with get_session() as s:
        u = s.scalars(select(User).where(User.email == email.strip().lower())).first()
        if not u:
            return False
        u.team_name = (team_name or None)
        s.commit()
        return True

def set_admin_flag(user_id: int, is_admin: bool) -> bool:
    with get_session() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        # admin unique
        u.is_admin = (u.email.strip().lower() == ADMIN_EMAIL)
        s.add(u); s.commit()
        return True
# ----- Suppression -----

def delete_user_by_id(user_id: int) -> bool:
    with get_session() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        s.delete(u)
        s.commit()
        return True

def delete_user_by_email(email: str) -> bool:
    with get_session() as s:
        u = s.scalars(select(User).where(User.email == email.strip().lower())).first()
        if not u:
            return False
        s.delete(u)
        s.commit()
        return True
    
# ----- Autres -----

def verify_password_by_email(email: str, raw_password: str) -> Tuple[bool, Optional[Dict]]:
    """
    Vérifie le mot de passe et renvoie (ok, user_public_dict) si succès.
    Gère bcrypt & pbkdf2, avec migration auto vers pbkdf2 si bcrypt détecté.
    """
    email = email.strip().lower()
    with get_session() as s:
        row = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not row:
            return False, None

        if not _verify_and_migrate_if_needed(row, raw_password, row.password_hash, s):
            return False, None

        return True, {"id": row.id, "email": row.email, "team_name": row.team_name, "is_admin": bool(row.is_admin)}
