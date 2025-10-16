# app/pages/0_🔐_Connexion.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import time
import streamlit as st

from services.auth_service import login, logout, current_user
from core.repos.users_repo import create_user

from ui.nav import sidebar_menu

st.set_page_config(page_title="Connexion", page_icon="🔐")
u = sidebar_menu()

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
    # anti-bruteforce minimal côté UI (en complément de auth_service)
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
user = current_user()
if user:
    st.success(f"Connecté en tant que {user['email']} (équipe : {user.get('team_name') or '—'})")
    if st.button("Se déconnecter"):
        logout()
        # (optionnel) on régénère le token après logout
        st.session_state.pop("csrf_token", None)
        st.rerun()
else:
    st.subheader("Se connecter")
    disabled = _cooldown_active()
    if disabled:
        st.warning("Trop de tentatives. Veuillez patienter quelques secondes avant de réessayer.", icon="⏳")

    with st.form("login", clear_on_submit=False):
        email = st.text_input("Email", disabled=disabled)
        pwd = st.text_input("Mot de passe", type="password", disabled=disabled)
        # ❌ Supprimé: aucun champ "CSRF" rendu à l'écran
        ok = st.form_submit_button("Se connecter", disabled=disabled)

    if ok and not disabled:
        # ✅ Vérifie le token directement depuis la session (sans champ utilisateur)
        if not _check_csrf(st.session_state.get("csrf_token")):
            st.error("CSRF invalide.")
        else:
            email_n = _norm_email(email)
            if not email_n or not pwd:
                st.error("Email et mot de passe sont requis.")
            else:
                if login(email_n, pwd):
                    _reset_fail()
                    # (optionnel) rotation du token à la connexion
                    st.session_state.pop("csrf_token", None)
                    _ensure_csrf()
                    st.success("Connexion réussie ✅")
                    st.rerun()
                else:
                    _register_fail()
                    st.error("Identifiants invalides.")

st.divider()


# ---------------------------
# Création de compte (active par défaut)
# ---------------------------
# Priorité : st.secrets > env ; défaut = True
_allow_secret = st.secrets.get("ALLOW_SELF_SIGNUP", None)
ALLOW_SELF_SIGNUP = (
    (_allow_secret if isinstance(_allow_secret, bool) else None)
)
if ALLOW_SELF_SIGNUP is None:
    # fallback env (string) puis défaut True
    ALLOW_SELF_SIGNUP = (os.getenv("ALLOW_SELF_SIGNUP", "true").strip().lower() in {"1", "true", "yes"})

with st.expander("🆕 Créer un utilisateur"):
    if not ALLOW_SELF_SIGNUP:
        st.info(
            "La création de compte est désactivée (ALLOW_SELF_SIGNUP=false). "
            "Activez-la côté serveur si nécessaire.",
            icon="🔒",
        )
    else:
        st.caption("Crée ton compte ci-dessous. (Le rôle **Admin** n’est attribué que si ton email correspond à `admin_email` côté serveur.)")
        with st.form("create_user"):
            email2 = st.text_input("Email (nouveau)")
            pwd2 = st.text_input("Mot de passe (nouveau)", type="password")
            team2 = st.text_input("Équipe (ex : Toulouse, Lyon)", placeholder="Toulouse")
            ok2 = st.form_submit_button("Créer mon compte")

        if ok2:
            # On récupère le token directement depuis la session (plus besoin de champ)
            token_ok = _check_csrf(st.session_state.get("csrf_token"))
            if not token_ok:
                st.error("CSRF invalide.")
            else:
                email2_n = _norm_email(email2)
                if not email2_n or not pwd2:
                    st.error("Email et mot de passe sont requis.")
                elif len(pwd2) < 8:
                    st.error("Le mot de passe doit contenir au moins 8 caractères.")
                else:
                    try:
                        uid = create_user(email2_n, pwd2, (team2.strip() or None))
                        st.success(f"Utilisateur créé avec succès (id={uid}) ✅")
                        st.info("Tu peux maintenant te connecter avec ce compte.")
                    except Exception as e:
                        st.error(str(e))
# ------------------------------

