# app/ui/nav.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from services.auth_service import current_user, logout


def sidebar_menu() -> dict | None:
    """
    Affiche le menu latéral et renvoie l'utilisateur courant (dict) ou None.
    À appeler en haut de chaque page.
    """
    u = current_user()

    with st.sidebar:
        st.header("🏉 Footy Score")

        if u:
            st.caption(f"Connecté : **{u['email']}**")
            if u.get("team_name"):
                st.caption(f"Équipe : **{u['team_name']}**")

            st.divider()
            st.page_link("pages/Historique.py", label="📚 Historique des matchs")
            st.page_link("pages/Saisie_post_match.py", label="📝 Saisie post-match")
            st.page_link("pages/Stats_saison.py", label="📊 Stats saison")
            st.page_link("pages/profil.py", label="👤 Profil")

            if u.get("is_admin"):
                st.page_link("pages/admin.py", label="🛠️ Administration")

            st.divider()
            if st.button("🚪 Se déconnecter", key="logout-btn-sidebar"):
                logout()
                st.success("Déconnexion réussie.")
                st.rerun()

            st.markdown("---")
            st.caption("💡 Conseil : utilisez le menu ci-dessus pour naviguer entre les pages.")
        else:
            # Non connecté → menu minimal
            st.page_link("pages/connexion.py", label="🔐 Connexion")
            st.info("Connectez-vous pour accéder aux autres pages.")

    return u


def landing_content(u: dict | None) -> None:
    """
    Contenu principal optionnel pour la page d’accueil (main.py).
    À utiliser UNIQUEMENT sur la page principale, pas sur les sous-pages.
    """
    if not u:
        st.title("🏉 Bienvenue sur Footy Score")
        st.write(
            "L’application idéale pour suivre les résultats, saisir les matchs et consulter "
            "les statistiques de ton équipe de footy préférée !"
        )
        st.info("👉 Connecte-toi depuis le menu latéral pour commencer.")
    else:
        st.title("📊 Tableau de bord Footy Score")
        st.write("Utilise le menu à gauche pour naviguer entre les sections de l’application.")
        if u.get("is_admin"):
            st.success("Mode administrateur activé ✅")
        st.markdown("---")
