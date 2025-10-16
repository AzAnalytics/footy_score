# app/pages/0a_🛠️_Admin.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import streamlit as st
import pandas as pd

from services.auth_service import require_admin, current_user  # renvoie un dict user
from core.repos.users_repo import (
    list_users,
    create_user,
    set_password,
    update_user_team,
    set_admin_flag,
    delete_user_by_id,
)
from ui.nav import sidebar_menu

# ---------------------------
# Page & config
# ---------------------------
st.set_page_config(page_title="Administration", page_icon="🛠️")
u = sidebar_menu()  # sidebar cohérente avec le reste
st.title("🛠️ Administration")

# ---------------------------
# Helpers sécurité
# ---------------------------
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or st.secrets.get("admin_email", "") or "").strip().lower()

def _ensure_csrf():
    if "csrf_token" not in st.session_state:
        import secrets
        st.session_state["csrf_token"] = secrets.token_urlsafe(24)
    return st.session_state["csrf_token"]

def _check_csrf() -> bool:
    # Vérifie simplement que le token de session existe (on ne le rend jamais à l'écran)
    return bool(st.session_state.get("csrf_token"))

def _auth_ctx() -> dict:
    u = current_user() or {}
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "team_name": u.get("team_name"),
        "is_admin": bool(u.get("is_admin")),
    }

# ---------------------------
# Auth stricte
# ---------------------------
admin = require_admin()  # st.stop() si non-admin
caller = _auth_ctx()
_ensure_csrf()

st.caption(f"Connecté en tant que **{admin['email']}** — rôle **Admin**")
st.info(f"Compte admin racine : `{ADMIN_EMAIL}` (défini côté serveur).", icon="🔐")
st.divider()

# =========================
# Section 1 — Vue d'ensemble
# =========================
st.subheader("👥 Utilisateurs")

try:
    users = list_users()
except Exception as e:
    users = []
    st.error(f"Impossible de lister les utilisateurs : {e}")

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
    st.caption("ℹ️ Seul l’email défini par `admin_email` (secrets) sera admin. Les autres sont créés non-admin.")
    submit_new = st.form_submit_button("Créer")

if submit_new:
    if not _check_csrf():
        st.error("CSRF invalide.")
    elif not email_new or not pwd_new:
        st.error("Email et mot de passe sont requis.")
    elif len(pwd_new) < 8:
        st.error("Le mot de passe doit contenir au moins 8 caractères.")
    else:
        try:
            uid = create_user(email_new.strip().lower(), pwd_new, (team_new.strip() or None))
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
            ok_team = st.form_submit_button("Mettre à jour l’équipe")
        if ok_team:
            if not _check_csrf():
                st.error("CSRF invalide.")
            else:
                if update_user_team(selected_user["email"], (team_edit or None)):
                    # si l'admin édite son propre compte, rafraîchir la session
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

        with st.form("edit_admin_form"):
            admin_edit = st.checkbox(
                "Administrateur ?",
                value=bool(selected_user.get("is_admin")),
                help="Seul le compte `admin_email` (secrets) peut être admin.",
            )
            ok_admin = st.form_submit_button("Mettre à jour les droits")

        if ok_admin:
            if not _check_csrf():
                st.error("CSRF invalide.")
            else:
                if is_root_target and (not admin_edit):
                    st.error("Impossible de retirer le droit admin au compte racine.")
                else:
                    if set_admin_flag(selected_user["id"], bool(admin_edit)):
                        au = st.session_state.get("auth_user") or {}
                        if au.get("email") == selected_user["email"]:
                            au["is_admin"] = (selected_user["email"].strip().lower() == ADMIN_EMAIL)
                            st.session_state["auth_user"] = au
                        st.success("Droits mis à jour ✅")
                        st.rerun()
                    else:
                        st.error("Échec de mise à jour des droits.")

        # --- Reset mot de passe ---
        st.markdown("#### 🔒 Réinitialiser le mot de passe")
        with st.form("reset_pwd_form"):
            new_pwd = st.text_input("Nouveau mot de passe", type="password")
            new_pwd2 = st.text_input("Confirmer le mot de passe", type="password")
            ok_pwd = st.form_submit_button("Réinitialiser")
        if ok_pwd:
            if not _check_csrf():
                st.error("CSRF invalide.")
            elif len(new_pwd) < 8:
                st.error("Le mot de passe doit contenir au moins 8 caractères.")
            elif new_pwd != new_pwd2:
                st.error("La confirmation ne correspond pas.")
            else:
                if set_password(selected_user["email"], new_pwd):
                    st.success("Mot de passe réinitialisé ✅")
                else:
                    st.error("Échec de réinitialisation du mot de passe.")

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
            elif not _check_csrf():
                st.error("CSRF invalide.")
            else:
                if delete_user_by_id(selected_user["id"]):
                    st.success("Utilisateur supprimé ✅")
                    st.rerun()
                else:
                    st.error("Échec de suppression.")
