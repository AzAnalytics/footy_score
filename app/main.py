# app/main.py
from __future__ import annotations
import streamlit as st
from core.db import init_db
from core.models import Base
from services.auth_service import current_user, logout

st.set_page_config(page_title="Footy Score", page_icon="🏉")
init_db(Base)

u = current_user()

# Rediriger vers Connexion si on arrive sur /main sans être connecté
try:
    if not u:
        st.switch_page("pages/Connexion.py")  # Streamlit >= 1.22
except Exception:
    pass  # si switch_page indisponible, on affiche juste le lien ci-dessous

with st.sidebar:
    st.header("Menu")
    if u:
        # Pages visibles quand on est connecté
        st.page_link("pages/Historique.py", label="Historique")
        st.page_link("pages/Saisie_post_match.py", label="Saisie post match")
        st.page_link("pages/Stats_saison.py", label="Stats saison")
        st.page_link("pages/profil.py", label="Profil")

        # Admin visible uniquement pour toi (ton email est déjà verrouillé côté repo)
        if u.get("is_admin"):
            st.page_link("pages/admin.py", label="Admin")

        st.divider()
        if st.button("Se déconnecter"):
            logout()
            st.rerun()
    else:
        # Quand on n'est PAS connecté : on ne montre QUE Connexion
        st.page_link("pages/connexion.py", label="Connexion")
        st.info("Veuillez vous connecter pour accéder aux autres pages.")

# Contenu de la page d’accueil (optionnel)
if not u:
    st.title("Bienvenue 👋")
    st.write("Merci de vous connecter pour accéder à l’application.")
else:
    st.title("🏉 Footy Score")
    st.write("Utilisez le menu à gauche pour naviguer.")
