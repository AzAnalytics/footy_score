# app/core/repos/users_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete, update
from passlib.hash import bcrypt

from core.db import get_session
from core.models import User

# ----- Lecture -----

def get_user_by_email(email: str) -> Optional[User]:
    with get_session() as s:
        return s.scalars(select(User).where(User.email == email.strip().lower())).first()

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
    if get_user_by_email(email):
        raise ValueError("Email déjà utilisé.")
    pwd_hash = bcrypt.hash(raw_password)
    u = User(email=email.strip().lower(), password_hash=pwd_hash, team_name=team_name, is_admin=is_admin)
    with get_session() as s:
        s.add(u)
        s.flush()
        new_id = u.id
        s.commit()
        return new_id

# ----- Mise à jour -----

def verify_password(user: User, raw_password: str) -> bool:
    return bcrypt.verify(raw_password, user.password_hash)

def set_password(email: str, new_raw_password: str) -> bool:
    with get_session() as s:
        u = s.scalars(select(User).where(User.email == email.strip().lower())).first()
        if not u:
            return False
        u.password_hash = bcrypt.hash(new_raw_password)
        s.commit()
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
        u.is_admin = bool(is_admin)
        s.commit()
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
