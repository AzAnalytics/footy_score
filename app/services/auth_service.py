# app/services/auth_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Callable
import streamlit as st

from core.repos.users_repo import get_user_by_email, verify_password

SESSION_KEY = "auth_user"  # dict: {"email":..., "team_name":..., "is_admin":...}

def login(email: str, password: str) -> bool:
    u = get_user_by_email(email.strip().lower())
    if not u:
        return False
    if not verify_password(u, password):
        return False
    st.session_state[SESSION_KEY] = {"email": u.email, "team_name": u.team_name, "is_admin": bool(u.is_admin), "id": u.id}
    return True

def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)

def current_user() -> Optional[dict]:
    return st.session_state.get(SESSION_KEY)

def require_login() -> Optional[dict]:
    user = current_user()
    if not user:
        st.warning("Veuillez vous connecter.")
        st.stop()
    return user

def require_admin() -> dict:
    user = require_login()
    if not user.get("is_admin"):
        st.error("Accès réservé à l’administrateur.")
        st.stop()
    return user
