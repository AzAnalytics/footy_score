# app/pages/0b_👤_Profil.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st

from core.db import init_db
from core.models import Base
from services.auth_service import require_login, logout
from core.repos.users_repo import (
    get_user_by_email,
    verify_password,
    update_user_team,
    set_password,
)

st.set_page_config(page_title="Profil", page_icon="👤")
st.title("👤 Mon profil")

init_db(Base)
user = require_login()  # stop() si non connecté

st.markdown(f"**Email :** `{user['email']}`")
st.markdown(f"**Équipe :** `{user.get('team_name') or '—'}`")
st.markdown(f"**Rôle :** {'Admin' if user.get('is_admin') else 'Utilisateur'}")

st.divider()
st.subheader("⚽ Mon équipe")

with st.form("form_team"):
    new_team = st.text_input("Nom de l’équipe", value=user.get("team_name") or "", placeholder="Ex: Toulouse, Lyon…").strip()
    ok_team = st.form_submit_button("Mettre à jour l’équipe")
if ok_team:
    if update_user_team(user["email"], new_team or None):
        # mettre à jour la session
        st.session_state["auth_user"]["team_name"] = (new_team or None)
        st.success("Équipe mise à jour ✅")
        st.rerun()
    else:
        st.error("Impossible de mettre à jour l’équipe.")

st.divider()
st.subheader("🔒 Changer mon mot de passe")

with st.form("form_pwd"):
    current_pwd = st.text_input("Mot de passe actuel", type="password")
    new_pwd = st.text_input("Nouveau mot de passe", type="password")
    new_pwd2 = st.text_input("Confirmer le nouveau mot de passe", type="password")
    ok_pwd = st.form_submit_button("Mettre à jour le mot de passe")

if ok_pwd:
    u = get_user_by_email(user["email"])
    if not u:
        st.error("Utilisateur introuvable.")
    elif not verify_password(u, current_pwd):
        st.error("Mot de passe actuel invalide.")
    elif len(new_pwd) < 8:
        st.error("Le nouveau mot de passe doit contenir au moins 8 caractères.")
    elif new_pwd != new_pwd2:
        st.error("La confirmation ne correspond pas.")
    else:
        if set_password(user["email"], new_pwd):
            st.success("Mot de passe mis à jour ✅")
        else:
            st.error("Échec de la mise à jour du mot de passe.")

st.divider()
st.subheader("🚪 Déconnexion")
if st.button("Se déconnecter"):
    logout()
    st.success("Déconnexion effectuée.")
    st.rerun()
