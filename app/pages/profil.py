# app/pages/profil.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st

from services.auth_service import require_login, logout, current_user
from core.repos.users_repo import (
    verify_password_by_email,   # bcrypt/pbkdf2 + migration auto
    update_user_team,
    set_password,
)

# (facultatif) menu custom
try:
    from ui.nav import sidebar_menu
    _u = sidebar_menu()
except Exception:
    pass

st.set_page_config(page_title="Profil", page_icon="👤")
st.title("👤 Mon profil")

user = require_login()  # stop() si non connecté

def _auth_ctx() -> dict:
    u = current_user() or {}
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "team_name": u.get("team_name"),
        "is_admin": bool(u.get("is_admin")),
    }

def _ensure_csrf():
    if "csrf_token" not in st.session_state:
        import secrets
        st.session_state["csrf_token"] = secrets.token_urlsafe(24)
    return st.session_state["csrf_token"]

def _check_csrf(token: str | None) -> bool:
    return bool(token and token == st.session_state.get("csrf_token"))

caller = _auth_ctx()
csrf = _ensure_csrf()

st.markdown(f"**Email :** `{user['email']}`")
st.markdown(f"**Équipe :** `{user.get('team_name') or '—'}`")
st.markdown(f"**Rôle :** {'Admin' if user.get('is_admin') else 'Utilisateur'}")

st.divider()
st.subheader("⚽ Mon équipe")

with st.form("form_team"):
    new_team = st.text_input(
        "Nom de l’équipe",
        value=user.get("team_name") or "",
        placeholder="Ex: Toulouse, Lyon…"
    )
    # CSRF caché
    ok_team = st.form_submit_button("Mettre à jour l’équipe")

if ok_team:
    if not _check_csrf(st.session_state.get("csrf_team")):
        st.error("CSRF invalide.")
    else:
        team_norm = (new_team or "").strip() or None
        if update_user_team(user["email"], team_norm, caller_ctx=caller):
            # mettre à jour la session si présente
            au = st.session_state.get("auth_user") or {}
            if au.get("email") == user["email"]:
                au["team_name"] = team_norm
                st.session_state["auth_user"] = au
            st.success("Équipe mise à jour ✅")
            st.rerun()
        else:
            st.error("Impossible de mettre à jour l’équipe (droits insuffisants).")

st.divider()
st.subheader("🔒 Changer mon mot de passe")

with st.form("form_pwd"):
    current_pwd = st.text_input("Mot de passe actuel", type="password")
    new_pwd = st.text_input("Nouveau mot de passe", type="password")
    new_pwd2 = st.text_input("Confirmer le nouveau mot de passe", type="password")
    # CSRF caché
    ok_pwd = st.form_submit_button("Mettre à jour le mot de passe")

if ok_pwd:
    if not _check_csrf(st.session_state.get("csrf_pwd")):
        st.error("CSRF invalide.")
    else:
        # Vérifie le mot de passe actuel via l’API unifiée
        ok, _ = verify_password_by_email(user["email"], current_pwd or "")
        if not ok:
            st.error("Mot de passe actuel invalide.")
        elif not new_pwd or len(new_pwd) < 8:
            st.error("Le nouveau mot de passe doit contenir au moins 8 caractères.")
        elif new_pwd != new_pwd2:
            st.error("La confirmation ne correspond pas.")
        else:
            if set_password(user["email"], new_pwd, caller_ctx=caller):
                st.success("Mot de passe mis à jour ✅")
            else:
                st.error("Échec de la mise à jour du mot de passe (droits insuffisants).")

st.divider()
st.subheader("🚪 Déconnexion")
if st.button("Se déconnecter"):
    logout()
    st.success("Déconnexion effectuée.")
    st.rerun()
