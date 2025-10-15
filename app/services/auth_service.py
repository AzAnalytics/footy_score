# app/services/auth_service.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional
import streamlit as st
import time
import secrets

from core.repos.users_repo import verify_password_by_email

# -----------------------------
# Constantes et clés session
# -----------------------------
SESSION_KEY = "auth_user"        # dict: {"email":..., "team_name":..., "is_admin":...}
FAIL_KEY = "auth_fails"          # liste timestamps des tentatives ratées
CSRF_KEY = "csrf_token"          # token CSRF pour formulaires sensibles
LAST_SEEN_KEY = "auth_last_seen" # timestamp dernière activité

# Sécurité brute-force : max 5 essais en 5 minutes
WINDOW = 300
LIMIT = 5

# Expiration de session (2 h par défaut)
SESSION_TTL = 2 * 3600


# -----------------------------
# Helpers internes
# -----------------------------
def _now() -> float:
    return time.time()


def _too_many_fails() -> bool:
    """Vérifie si trop de tentatives ont échoué récemment."""
    now = _now()
    fails = [t for t in st.session_state.get(FAIL_KEY, []) if now - t < WINDOW]
    st.session_state[FAIL_KEY] = fails
    return len(fails) >= LIMIT


def _record_fail() -> None:
    st.session_state.setdefault(FAIL_KEY, []).append(_now())


def _reset_fails() -> None:
    st.session_state.pop(FAIL_KEY, None)


def _issue_csrf() -> str:
    """Renvoie ou génère un token CSRF unique pour cette session."""
    if CSRF_KEY not in st.session_state:
        st.session_state[CSRF_KEY] = secrets.token_urlsafe(24)
    return st.session_state[CSRF_KEY]


def _expire_session_if_needed() -> None:
    """Expire la session après inactivité prolongée."""
    last_seen = st.session_state.get(LAST_SEEN_KEY)
    now = _now()
    if last_seen and (now - last_seen) > SESSION_TTL:
        logout()
        st.warning("Session expirée, veuillez vous reconnecter.")
        st.stop()
    st.session_state[LAST_SEEN_KEY] = now


# -----------------------------
# Authentification principale
# -----------------------------
def login(email: str, password: str) -> bool:
    """Tente de connecter un utilisateur. Retourne True si succès."""
    if _too_many_fails():
        st.error("Trop de tentatives. Réessayez dans quelques minutes.")
        return False

    email_norm = (email or "").strip().lower()
    ok, user_public = verify_password_by_email(email_norm, password or "")
    if not ok:
        _record_fail()
        st.error("Identifiants invalides.")
        return False

    _reset_fails()
    st.session_state[SESSION_KEY] = user_public
    st.session_state[LAST_SEEN_KEY] = _now()
    _issue_csrf()

    # Audit minimal
    if user_public.get("is_admin"):
        print(f"[SECURITY] Admin {email_norm} connecté à {time.strftime('%Y-%m-%d %H:%M:%S')}")

    return True


def logout() -> None:
    """Supprime toute donnée d’authentification de la session."""
    for k in [SESSION_KEY, FAIL_KEY, CSRF_KEY, LAST_SEEN_KEY]:
        st.session_state.pop(k, None)


def current_user() -> Optional[dict]:
    """Renvoie le user courant s’il existe, sinon None."""
    user = st.session_state.get(SESSION_KEY)
    if user:
        _expire_session_if_needed()
    return user


def is_logged_in() -> bool:
    """Renvoie True si un utilisateur est actuellement connecté."""
    return bool(current_user())


def is_admin() -> bool:
    """Renvoie True si l’utilisateur courant est admin."""
    u = current_user()
    return bool(u and u.get("is_admin"))


def require_login() -> dict:
    """Stoppe Streamlit si aucun utilisateur n’est connecté."""
    u = current_user()
    if not u:
        st.warning("Veuillez vous connecter pour accéder à cette page.")
        st.stop()
    return u


def require_admin() -> dict:
    """Stoppe Streamlit si l’utilisateur n’est pas admin."""
    u = require_login()
    if not u.get("is_admin"):
        st.error("Accès réservé à l’administrateur.")
        st.stop()
    return u


def get_csrf_token() -> str:
    """Expose le token CSRF courant."""
    return _issue_csrf()


def check_csrf(token: str | None) -> bool:
    """Vérifie la validité d’un token CSRF reçu."""
    return bool(token and token == st.session_state.get(CSRF_KEY))
# ---------------------------------------------------------------------------
# Fin du service d’authentification
# ---------------------------------------------------------------------------