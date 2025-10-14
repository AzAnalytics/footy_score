# app/pages/0_🔐_Connexion.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from core.db import init_db
from core.models import Base
from services.auth_service import login, logout, current_user
from core.repos.users_repo import create_user

st.set_page_config(page_title="Connexion", page_icon="🔐")
st.title("🔐 Connexion")

init_db(Base)

u = current_user()
if u:
    st.success(f"Connecté en tant que {u['email']} (équipe: {u.get('team_name') or '—'})")
    if st.button("Se déconnecter"):
        logout()
        st.rerun()
else:
    with st.form("login"):
        email = st.text_input("Email")
        pwd = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Se connecter")
    if ok:
        if login(email, pwd):
            st.success("Connexion réussie.")
            st.rerun()
        else:
            st.error("Identifiants invalides.")

st.divider()
with st.expander("Créer un utilisateur (setup initial)"):
    st.caption("À désactiver/retirer en prod ou protéger par un compte admin.")
    with st.form("create_user"):
        email2 = st.text_input("Email (nouveau)")
        pwd2 = st.text_input("Mot de passe (nouveau)", type="password")
        team2 = st.text_input("Équipe (ex: Toulouse, Lyon)", placeholder="Toulouse")
        is_admin = st.checkbox("Administrateur ?", value=False)
        ok2 = st.form_submit_button("Créer")
    if ok2:
        try:
            uid = create_user(email2, pwd2, team2.strip() or None, is_admin=is_admin)
            st.success(f"Utilisateur créé (id={uid}).")
        except Exception as e:
            st.error(str(e))
        st.info("Vous pouvez maintenant vous connecter avec ce compte.")