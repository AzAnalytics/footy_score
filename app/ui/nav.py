# app/ui/nav.py
from __future__ import annotations
import streamlit as st
from services.auth_service import current_user, logout

def sidebar_menu() -> dict | None:
    """
    Affiche le menu latéral custom et renvoie l'utilisateur courant (dict) ou None.
    À appeler AU DÉBUT de chaque page.
    """
    u = current_user()

    with st.sidebar:
        st.header("Menu")
        if u:
            # Pages visibles quand on est connecté
            st.page_link("pages/Historique.py", label="Historique")
            st.page_link("pages/Saisie_post_match.py", label="Saisie post match")
            st.page_link("pages/Stats_saison.py", label="Stats saison")
            st.page_link("pages/profil.py", label="Profil")

            # Admin visible uniquement pour toi (déjà verrouillé côté repo)
            if u.get("is_admin"):
                st.page_link("pages/admin.py", label="Admin")

            st.divider()
            if st.button("Se déconnecter", key="logout-btn"):
                logout()
                st.rerun()
        else:
            # Quand on n'est PAS connecté : on ne montre QUE Connexion
            st.page_link("pages/connexion.py", label="Connexion")
            st.info("Veuillez vous connecter pour accéder aux autres pages.")

    return u


def landing_content(u: dict | None) -> None:
    """
    Entête optionnelle : page d’accueil (main) selon l’état de connexion.
    Utilise-la uniquement sur main.py. Les autres pages gardent leur propre titre.
    """
    if not u:
        st.title("Bienvenue dans footy score, la meilleur app pour suivre tous les résultats de votre équipe favorite 👋")
        st.write("Merci de vous connecter pour accéder à l’application.")
    else:
        st.title("🏉 Footy Score")
        st.write("Utilisez le menu à gauche pour naviguer.")
