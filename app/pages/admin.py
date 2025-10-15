# app/pages/0a_🛠️_Admin.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import streamlit as st
import pandas as pd

from core.models import Base
from services.auth_service import require_admin, current_user  # doit renvoyer un dict user
from core.repos.users_repo import (
    list_users,
    create_user,
    set_password,
    update_user_team,
    set_admin_flag,
    delete_user_by_id,
)

# ---------------------------
# Config & helpers sécurité
# ---------------------------

ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "az.analytics.pro@gmail.com").strip().lower()

def _ensure_csrf():
    if "csrf_token" not in st.session_state:
        import secrets
        st.session_state["csrf_token"] = secrets.token_urlsafe(24)
    return st.session_state["csrf_token"]

def _check_csrf(token: str | None) -> bool:
    return bool(token and token == st.session_state.get("csrf_token"))

def _auth_ctx() -> dict:
    # Adapte si ton current_user() retourne autre chose
    u = current_user() or {}
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "team_name": u.get("team_name"),
        "is_admin": bool(u.get("is_admin")),
    }

# ---------------------------
# Page
# ---------------------------

st.set_page_config(page_title="Administration", page_icon="🛠️")
st.title("🛠️ Administration")

# Auth stricte
admin = require_admin()  # stop() si non-admin
caller = _auth_ctx()

st.caption(f"Connecté en tant que **{admin['email']}** — rôle **Admin**")
st.info(f"Compte admin racine : `{ADMIN_EMAIL}` (défini via la variable d’environnement ADMIN_EMAIL).", icon="🔐")

csrf = _ensure_csrf()
st.divider()

# =========================
# Section 1 — Vue d'ensemble
# =========================
st.subheader("👥 Utilisateurs")

users = list_users(caller_ctx=caller)
df = pd.DataFrame(users)
if df.empty:
    st.info("Aucun utilisateur.")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export CSV", data=csv_bytes, file_name="users.csv", mime="text/csv")

st.divider()

# =========================
# Section 2 — Créer un utilisateur
# =========================
st.subheader("➕ Créer un utilisateur")

with st.form("create_user_form"):
    c1, c2 = st.columns(2)
    email_new = c1.text_input("Email")
    team_new = c2.text_input("Équipe (optionnel)", placeholder="Toulouse / Lyon / …")
    pwd_new = st.text_input("Mot de passe", type="password")
    st.caption("ℹ️ Seul l’email défini par ADMIN_EMAIL sera admin. Les autres comptes sont créés non-admin.")
    # CSRF
    st.text_input("CSRF", value=csrf, type="password", key="csrf_create", label_visibility="collapsed")
    submit_new = st.form_submit_button("Créer")

if submit_new:
    if not _check_csrf(st.session_state.get("csrf_create")):
        st.error("CSRF invalide.")
    elif not email_new or not pwd_new:
        st.error("Email et mot de passe sont requis.")
    elif len(pwd_new) < 8:
        st.error("Le mot de passe doit contenir au moins 8 caractères.")
    else:
        try:
            uid = create_user(email_new, pwd_new, (team_new or None), caller_ctx=caller)
            st.success(f"Utilisateur créé (id={uid}).")
            st.rerun()
        except Exception as e:
            st.error(str(e))

st.divider()

# =========================
# Section 3 — Éditer un utilisateur
# =========================
st.subheader("✏️ Éditer un utilisateur")

if not users:
    st.info("Ajoutez d’abord un utilisateur.")
else:
    # Sélection par email ou ID
    by = st.radio("Sélectionner par :", ["Email", "ID"], horizontal=True)
    selected_user = None

    if by == "Email":
        emails = [u["email"] for u in users]
        email_sel = st.selectbox("Utilisateur (email)", emails, index=0 if emails else None)
        selected_user = next((u for u in users if u["email"] == email_sel), None)
    else:
        ids = [u["id"] for u in users]
        id_sel = st.selectbox("Utilisateur (ID)", ids, index=0 if ids else None)
        selected_user = next((u for u in users if u["id"] == id_sel), None)

    if not selected_user:
        st.warning("Aucun utilisateur sélectionné.")
    else:
        st.markdown(
            f"**ID :** `{selected_user['id']}`  •  **Email :** `{selected_user['email']}`  "
            f"•  **Équipe :** `{selected_user.get('team_name') or '—'}`  "
            f"•  **Admin :** `{selected_user.get('is_admin')}`"
        )

        # --- Edit équipe ---
        st.markdown("#### ⚽ Modifier l’équipe")
        with st.form("edit_team_form"):
            team_edit = st.text_input("Équipe", value=selected_user.get("team_name") or "", placeholder="Ex: Toulouse")
            st.text_input("CSRF", value=csrf, type="password", key="csrf_team", label_visibility="collapsed")
            ok_team = st.form_submit_button("Mettre à jour l’équipe")
        if ok_team:
            if not _check_csrf(st.session_state.get("csrf_team")):
                st.error("CSRF invalide.")
            else:
                if update_user_team(selected_user["email"], (team_edit or None), caller_ctx=caller):
                    # si l'admin édite son propre compte, on rafraîchit la session si présente
                    au = st.session_state.get("auth_user") or {}
                    if au.get("email") == selected_user["email"]:
                        au["team_name"] = (team_edit or None)
                        st.session_state["auth_user"] = au
                    st.success("Équipe mise à jour ✅")
                    st.rerun()
                else:
                    st.error("Échec de mise à jour de l’équipe.")

        # --- Edit rôle admin ---
        st.markdown("#### 👑 Droits administrateur")
        is_root_target = selected_user["email"].strip().lower() == ADMIN_EMAIL

        # On autorise le toggle dans l’UI mais on explique la règle:
        # - Seul ADMIN_EMAIL peut être admin; les autres restent False.
        with st.form("edit_admin_form"):
            admin_edit = st.checkbox(
                "Administrateur ?",
                value=bool(selected_user.get("is_admin")),
                help="Seul le compte défini par ADMIN_EMAIL peut être admin.",
            )
            st.text_input("CSRF", value=csrf, type="password", key="csrf_admin", label_visibility="collapsed")
            ok_admin = st.form_submit_button("Mettre à jour les droits")

        if ok_admin:
            if not _check_csrf(st.session_state.get("csrf_admin")):
                st.error("CSRF invalide.")
            else:
                # On empêche de se retirer soi-même le rôle si on est le root admin
                if is_root_target and (not admin_edit):
                    st.error("Impossible de retirer le droit admin au compte racine.")
                else:
                    if set_admin_flag(selected_user["id"], bool(admin_edit), caller_ctx=caller):
                        # si on édite son propre rôle : actualiser la session si présente
                        au = st.session_state.get("auth_user") or {}
                        if au.get("email") == selected_user["email"]:
                            # recalcul depuis repo : seul ADMIN_EMAIL est admin
                            au["is_admin"] = (selected_user["email"].strip().lower() == ADMIN_EMAIL)
                            st.session_state["auth_user"] = au
                        st.success("Droits mis à jour ✅")
                        st.rerun()
                    else:
                        st.error("Échec de mise à jour des droits (règles d’accès).")

        # --- Reset mot de passe ---
        st.markdown("#### 🔒 Réinitialiser le mot de passe")
        with st.form("reset_pwd_form"):
            new_pwd = st.text_input("Nouveau mot de passe", type="password")
            new_pwd2 = st.text_input("Confirmer le mot de passe", type="password")
            st.text_input("CSRF", value=csrf, type="password", key="csrf_pwd", label_visibility="collapsed")
            ok_pwd = st.form_submit_button("Réinitialiser")
        if ok_pwd:
            if not _check_csrf(st.session_state.get("csrf_pwd")):
                st.error("CSRF invalide.")
            elif len(new_pwd) < 8:
                st.error("Le mot de passe doit contenir au moins 8 caractères.")
            elif new_pwd != new_pwd2:
                st.error("La confirmation ne correspond pas.")
            else:
                if set_password(selected_user["email"], new_pwd, caller_ctx=caller):
                    st.success("Mot de passe réinitialisé ✅")
                else:
                    st.error("Échec de réinitialisation (droits insuffisants).")

        # --- Suppression utilisateur ---
        st.markdown("#### 🗑️ Supprimer l’utilisateur")
        c1, c2 = st.columns(2)
        with c1:
            confirm_email = st.text_input("Tapez l’email pour confirmer :", key="confirm_email")
        with c2:
            danger = st.button("Supprimer définitivement", type="secondary")
        if danger:
            if confirm_email.strip().lower() != selected_user["email"].strip().lower():
                st.error("Confirmez en retapant l’email exact de l’utilisateur.")
            else:
                # CSRF simple pour le bouton (saisie invisible à côté)
                if not _check_csrf(csrf):
                    st.error("CSRF invalide.")
                else:
                    if delete_user_by_id(selected_user["id"], caller_ctx=caller):
                        st.success("Utilisateur supprimé ✅")
                        st.rerun()
                    else:
                        st.error("Échec de suppression (droits insuffisants ou compte protégé).")
