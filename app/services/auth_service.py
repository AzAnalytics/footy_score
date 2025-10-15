# app/services/auth_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Callable
import streamlit as st

from core.repos.users_repo import get_user_by_email, verify_password, verify_password_by_email

SESSION_KEY = "auth_user"  # dict: {"email":..., "team_name":..., "is_admin":...}

def login(email: str, password: str) -> bool:
    ok, user_public = verify_password_by_email(email, password)
    if not ok:
        return False
    st.session_state[SESSION_KEY] = user_public  # dict prêt à l’emploi
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
