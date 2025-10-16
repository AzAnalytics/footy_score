# app/main.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st

from services.auth_service import current_user
from ui.nav import sidebar_menu, landing_content

st.set_page_config(page_title="Footy Score", page_icon="🏉")

# État de connexion
u = current_user()

# Redirection vers Connexion si non connecté (si dispo)
if not u:
    try:
        # Nom du fichier exact de la page de connexion
        st.switch_page("pages/connexion.py")  # Streamlit >= 1.22
    except Exception:
        # Fallback : on reste sur main et on affiche le lien + contenu d’accueil
        pass

# Sidebar + entête d’accueil
sidebar_menu()
landing_content(u)
