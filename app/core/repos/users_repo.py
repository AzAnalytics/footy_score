# app/core/repos/users_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple

import os
import re
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from passlib.hash import pbkdf2_sha256, bcrypt

from core.db import get_session
from core.models import User

# ---------------------------------------------------------------------------
# Configuration & helpers
# ---------------------------------------------------------------------------

ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "az.analytics.pro@gmail.com").strip().lower()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _norm_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not e or not _EMAIL_RE.match(e):
        raise ValueError("Email invalide.")
    return e

def _norm_team(team_name: Optional[str]) -> Optional[str]:
    if team_name is None:
        return None
    s = str(team_name).strip()
    return s[:80] or None

def _norm_password(pwd: str) -> str:
    if not isinstance(pwd, str):
        raise ValueError("Mot de passe invalide.")
    if not (8 <= len(pwd) <= 256):
        raise ValueError("Le mot de passe doit contenir entre 8 et 256 caractères.")
    return pwd

def _hash_password(raw: str) -> str:
    # PBKDF2-SHA256: robuste, pas de limite 72o (contrairement à bcrypt)
    return pbkdf2_sha256.hash(raw)

def _is_bcrypt(hash_: str) -> bool:
    return hash_.startswith(("$2a$", "$2b$", "$2y$"))

def _is_admin_ctx(user_ctx: Optional[dict]) -> bool:
    return bool((user_ctx or {}).get("is_admin"))

def _is_self_ctx(user_ctx: Optional[dict], user: User) -> bool:
    uid = (user_ctx or {}).get("id")
    return bool(uid) and int(uid) == int(user.id)

def _verify_and_migrate_if_needed(user: User, raw_password: str, hash_: str, session) -> bool:
    """
    Vérifie le hash (bcrypt ou pbkdf2). Si bcrypt OK => réécriture silencieuse en PBKDF2.
    Tolère les échecs bcrypt (mots de passe >72 o, etc.).
    """
    if _is_bcrypt(hash_):
        try:
            if len(raw_password.encode("utf-8")) > 72:
                return False
            ok = bcrypt.verify(raw_password, hash_)
        except Exception:
            return False

        if ok:
            user.password_hash = _hash_password(raw_password)
            session.add(user)
            session.commit()
        return ok
    else:
        return pbkdf2_sha256.verify(raw_password, hash_)

# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def get_user_by_email(email: str, *, caller_ctx: Optional[dict] = None) -> Optional[User]:
    # Admin only (évite l'énumération d'emails)
    if not _is_admin_ctx(caller_ctx):
        return None
    email = _norm_email(email)
    with get_session() as s:
        return s.scalars(select(User).where(User.email == email)).first()

def get_user_by_id(user_id: int, *, caller_ctx: Optional[dict] = None) -> Optional[User]:
    # Admin only
    if not _is_admin_ctx(caller_ctx):
        return None
    with get_session() as s:
        return s.get(User, user_id)

def list_users(*, caller_ctx: Optional[dict] = None) -> List[Dict[str, Any]]:
    # Admin only
    if not _is_admin_ctx(caller_ctx):
        return []
    with get_session() as s:
        rows = s.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "team_name": u.team_name,
                "is_admin": bool(u.is_admin),
                "created_at": u.created_at,
            }
            for u in rows
        ]

# ---------------------------------------------------------------------------
# Création
# ---------------------------------------------------------------------------

def _is_first_user(session) -> bool:
    cnt = session.execute(select(func.count(User.id))).scalar() or 0
    return int(cnt) == 0

def create_user(email: str, raw_password: str, team_name: Optional[str] = None, *, caller_ctx: Optional[dict] = None) -> int:
    """
    Règles:
    - Premier utilisateur: s'il correspond à ADMIN_EMAIL => admin; sinon non-admin.
    - Sinon: création autorisée si admin OU self-signup autorisé (ici on autorise).
      Dans tous les cas, seul l'email ADMIN_EMAIL obtient is_admin=True.
    """
    email_n = _norm_email(email)
    pwd = _norm_password(raw_password)
    team_n = _norm_team(team_name)

    with get_session() as s:
        existing = s.scalars(select(User).where(User.email == email_n)).first()
        if existing:
            raise ValueError("Email déjà utilisé.")

        is_first = _is_first_user(s)
        is_admin = (email_n == ADMIN_EMAIL) and (is_first or _is_admin_ctx(caller_ctx))

        u = User(email=email_n, password_hash=_hash_password(pwd), team_name=team_n, is_admin=is_admin)
        s.add(u)
        s.flush()
        uid = u.id
        s.commit()
        return uid

# ---------------------------------------------------------------------------
# Mise à jour
# ---------------------------------------------------------------------------

def set_password(email: str, new_raw_password: str, *, caller_ctx: Optional[dict] = None) -> bool:
    """
    Un admin peut changer n'importe quel mot de passe.
    Un utilisateur peut changer le sien (self-service).
    """
    email_n = _norm_email(email)
    pwd = _norm_password(new_raw_password)

    with get_session() as s:
        u = s.scalars(select(User).where(User.email == email_n)).first()
        if not u:
            return False
        if not (_is_admin_ctx(caller_ctx) or _is_self_ctx(caller_ctx, u)):
            return False
        u.password_hash = _hash_password(pwd)
        s.add(u)
        s.commit()
        return True

def update_user_team(email: str, team_name: Optional[str], *, caller_ctx: Optional[dict] = None) -> bool:
    """
    Un admin peut modifier l'équipe de n'importe qui.
    Un utilisateur peut modifier sa propre équipe.
    """
    email_n = _norm_email(email)
    team_n = _norm_team(team_name)
    with get_session() as s:
        u = s.scalars(select(User).where(User.email == email_n)).first()
        if not u:
            return False
        if not (_is_admin_ctx(caller_ctx) or _is_self_ctx(caller_ctx, u)):
            return False
        u.team_name = team_n
        s.commit()
        return True

def set_admin_flag(user_id: int, is_admin: bool, *, caller_ctx: Optional[dict] = None) -> bool:
    """
    Admin only. L'admin est uniquement le compte ADMIN_EMAIL.
    Si is_admin=True mais email != ADMIN_EMAIL => ignoré (reste False).
    Si is_admin=False et email == ADMIN_EMAIL => reste True (protégé).
    """
    if not _is_admin_ctx(caller_ctx):
        return False
    with get_session() as s:
        u = s.get(User, user_id)
        if not u:
            return False

        if u.email.strip().lower() == ADMIN_EMAIL:
            u.is_admin = True  # admin "racine" protégé
        else:
            u.is_admin = False  # personne d'autre ne peut être admin via ce repo
        s.add(u)
        s.commit()
        return True

# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------

def delete_user_by_id(user_id: int, *, caller_ctx: Optional[dict] = None) -> bool:
    """
    Admin only. Interdit de supprimer le compte ADMIN_EMAIL.
    Un utilisateur peut se supprimer lui-même (optionnel) — ici, on l'autorise.
    """
    with get_session() as s:
        u = s.get(User, user_id)
        if not u:
            return False

        # Protection du compte admin
        if u.email.strip().lower() == ADMIN_EMAIL:
            return False

        # Règles d'accès
        if not (_is_admin_ctx(caller_ctx) or _is_self_ctx(caller_ctx, u)):
            return False

        s.delete(u)
        s.commit()
        return True

def delete_user_by_email(email: str, *, caller_ctx: Optional[dict] = None) -> bool:
    with get_session() as s:
        email_n = _norm_email(email)
        u = s.scalars(select(User).where(User.email == email_n)).first()
        if not u:
            return False

        if u.email.strip().lower() == ADMIN_EMAIL:
            return False

        if not (_is_admin_ctx(caller_ctx) or _is_self_ctx(caller_ctx, u)):
            return False

        s.delete(u)
        s.commit()
        return True

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def verify_password_by_email(email: str, raw_password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Vérifie le mot de passe et renvoie (ok, user_public_dict) si succès.
    Gère bcrypt & pbkdf2, avec migration auto vers pbkdf2 si bcrypt détecté.
    """
    email_n = _norm_email(email)
    raw = str(raw_password)

    with get_session() as s:
        user = s.execute(select(User).where(User.email == email_n)).scalar_one_or_none()
        if not user:
            return False, None

        if not _verify_and_migrate_if_needed(user, raw, user.password_hash, s):
            return False, None

        # Recalcule is_admin à la volée (au cas où ADMIN_EMAIL a changé)
        is_admin = (user.email.strip().lower() == ADMIN_EMAIL)
        if user.is_admin != is_admin:
            user.is_admin = is_admin
            s.add(user)
            s.commit()

        return True, {
            "id": user.id,
            "email": user.email,
            "team_name": user.team_name,
            "is_admin": bool(user.is_admin),
        }
