# app/pages/2_📚_Historique.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from types import SimpleNamespace as _NS

from core.db import init_db
from core.models import Base
from core.repos.matches_repo import list_matches, get_match

# UI tables
from ui.tables import (
    matches_table,
    match_header,
    quarters_table,
    players_stats_table_view,
)

st.set_page_config(page_title="Historique", page_icon="📚")
st.title("📚 Historique des matchs")

init_db(Base)

# Récupère les N derniers matchs (liste de dicts)
rows = list_matches(100)

if not rows:
    st.info("Aucun match enregistré.")
else:
    # ---- Vue synthétique : tableau des matchs ----
    match_objs = [_NS(**m) for m in rows]
    matches_table(match_objs, title="📜 Récapitulatif des matchs", show_download=True)

    st.markdown("---")

    # ---- Détail par match (expanders) ----
    for m in rows:
        header = f"{m['date']} — {m['home_club']} {m['total_home_points']} – {m['total_away_points']} {m['away_club']}"
        with st.expander(header, expanded=False):
            st.caption(f"Saison {m['season_id']} • Lieu : {m.get('venue') or '—'} • ID: {m['id']}")

            # Charger le détail (quarts + stats) au besoin
            detail = get_match(m["id"])
            if not detail:
                st.warning("Détails indisponibles.")
                continue

            # Convertir en objets simples pour compat ui.table.*
            # On crée un objet match léger avec les champs principaux
            match_obj = _NS(
                id=detail.get("id"),
                date=detail.get("date"),
                season_id=detail.get("season_id"),
                home_club=detail.get("home_club"),
                away_club=detail.get("away_club"),
                venue=detail.get("venue"),
                total_home_points=detail.get("total_home_points"),
                total_away_points=detail.get("total_away_points"),
                # Champs G/B totaux optionnels (si disponibles dans le modèle)
                total_home_goals=detail.get("total_home_goals"),
                total_home_behinds=detail.get("total_home_behinds"),
                total_away_goals=detail.get("total_away_goals"),
                total_away_behinds=detail.get("total_away_behinds"),
            )

            # En-tête match compact (utilise scoreline si dispo)
            match_header(match_obj, show_scoreline=True)

            # Quarts-temps
            qs = detail.get("quarters", []) or []
            if qs:
                st.markdown("### 🧮 Quarts-temps")
                q_objs = [_NS(**q) for q in qs]
                quarters_table(q_objs, home_label=match_obj.home_club, away_label=match_obj.away_club, show_download=True)
            else:
                st.info("Aucun quart-temps enregistré pour ce match.")

            # Stats joueurs (Toulouse)
            pstats = detail.get("player_stats", []) or []
            if pstats:
                st.markdown("### 👥 Stats joueurs (Toulouse)")
                # players_stats_table_view accepte objets ou dicts : on peut passer la liste telle quelle
                players_stats_table_view(pstats, team_label="Toulouse", show_total=True, show_download=True)
            else:
                st.info("Aucune stat joueur enregistrée pour ce match.")

        st.markdown("---")

# ---------- FIN ----------
