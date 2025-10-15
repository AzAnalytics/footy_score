# app/pages/0_🔐_Connexion.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import time
import streamlit as st

from services.auth_service import login, logout, current_user
from core.repos.users_repo import create_user

from ui.nav import sidebar_menu
u = sidebar_menu()

st.set_page_config(page_title="Connexion", page_icon="🔐")
st.title("🔐 Connexion")

# ---------------------------
# Helpers sécurité
# ---------------------------
def _ensure_csrf():
    if "csrf_token" not in st.session_state:
        import secrets
        st.session_state["csrf_token"] = secrets.token_urlsafe(24)
    return st.session_state["csrf_token"]

def _check_csrf(token: str | None) -> bool:
    return bool(token and token == st.session_state.get("csrf_token"))

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()

def _cooldown_active() -> bool:
    # anti-bruteforce minimal côté UI
    now = time.time()
    last_fail = st.session_state.get("last_login_fail_ts", 0.0)
    fails = int(st.session_state.get("login_fail_count", 0))
    # après 5 échecs: cooldown 10s; après 10: 60s
    if fails >= 10 and (now - last_fail) < 60:
        return True
    if fails >= 5 and (now - last_fail) < 10:
        return True
    return False

def _register_fail():
    st.session_state["login_fail_count"] = int(st.session_state.get("login_fail_count", 0)) + 1
    st.session_state["last_login_fail_ts"] = time.time()

def _reset_fail():
    st.session_state["login_fail_count"] = 0
    st.session_state["last_login_fail_ts"] = 0.0

csrf = _ensure_csrf()

# ---------------------------
# Connexion / Déconnexion
# ---------------------------
u = current_user()
if u:
    st.success(f"Connecté en tant que {u['email']} (équipe : {u.get('team_name') or '—'})")
    if st.button("Se déconnecter"):
        logout()
        st.rerun()
else:
    st.subheader("Se connecter")
    disabled = _cooldown_active()
    if disabled:
        st.warning("Trop de tentatives. Veuillez patienter quelques secondes avant de réessayer.", icon="⏳")

    with st.form("login", clear_on_submit=False):
        email = st.text_input("Email", disabled=disabled)
        pwd = st.text_input("Mot de passe", type="password", disabled=disabled)
        # CSRF caché
        st.text_input("CSRF", value=csrf, type="password", key="csrf_login", label_visibility="collapsed")
        ok = st.form_submit_button("Se connecter", disabled=disabled)

    if ok and not disabled:
        if not _check_csrf(st.session_state.get("csrf_login")):
            st.error("CSRF invalide.")
        else:
            email_n = _norm_email(email)
            if not email_n or not pwd:
                st.error("Email et mot de passe sont requis.")
            else:
                if login(email_n, pwd):
                    _reset_fail()
                    st.success("Connexion réussie ✅")
                    st.rerun()
                else:
                    _register_fail()
                    st.error("Identifiants invalides.")

st.divider()

# ---------------------------
# Création de compte (optionnelle)
# ---------------------------
ALLOW_SELF_SIGNUP = (os.getenv("ALLOW_SELF_SIGNUP", "false").strip().lower() in {"1", "true", "yes"})

with st.expander("Créer un utilisateur"):
    if not ALLOW_SELF_SIGNUP:
        st.info("La création de compte est désactivée (ALLOW_SELF_SIGNUP=false). Activez-la côté serveur pour le setup initial.", icon="🔒")
    else:
        st.caption("À désactiver une fois l'application configurée (voir variable d'environnement ALLOW_SELF_SIGNUP).")
        with st.form("create_user"):
            email2 = st.text_input("Email (nouveau)")
            pwd2 = st.text_input("Mot de passe (nouveau)", type="password")
            team2 = st.text_input("Équipe (ex : Toulouse, Lyon)", placeholder="Toulouse")
            # CSRF caché
            st.text_input("CSRF", value=csrf, type="password", key="csrf_create", label_visibility="collapsed")
            ok2 = st.form_submit_button("Créer")
        if ok2:
            if not _check_csrf(st.session_state.get("csrf_create")):
                st.error("CSRF invalide.")
            else:
                email2_n = _norm_email(email2)
                if not email2_n or not pwd2:
                    st.error("Email et mot de passe sont requis.")
                elif len(pwd2) < 8:
                    st.error("Le mot de passe doit contenir au moins 8 caractères.")
                else:
                    try:
                        # ⚙️ Le backend attribue le rôle admin uniquement si l'email = ADMIN_EMAIL
                        caller = u or {}  # si quelqu'un est connecté (admin), on transmet
                        uid = create_user(email2_n, pwd2, (team2.strip() or None), caller_ctx=caller)
                        st.success(f"Utilisateur créé avec succès (id={uid}) ✅")
                        st.info("Vous pouvez maintenant vous connecter avec ce compte.")
                    except Exception as e:
                        st.error(str(e))
