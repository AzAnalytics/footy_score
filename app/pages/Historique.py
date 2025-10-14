# app/pages/2_📚_Historique.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from core.db import init_db
from core.models import Base
from core.repos.matches_repo import list_matches, get_match

st.set_page_config(page_title="Historique", page_icon="📚")
st.title("📚 Historique des matchs")

init_db(Base)

rows = list_matches(100)  # -> liste de dicts
if not rows:
    st.info("Aucun match enregistré.")
else:
    for m in rows:
        header = f"{m['date']} — {m['home_club']} {m['total_home_points']} – {m['total_away_points']} {m['away_club']}"
        with st.expander(header, expanded=False):
            st.caption(f"Saison {m['season_id']} • Lieu : {m.get('venue') or '—'} • ID: {m['id']}")

            # Charger le détail (quarts + stats) au besoin
            detail = get_match(m["id"])
            if not detail:
                st.warning("Détails indisponibles.")
                continue

            qs = detail.get("quarters", [])
            if qs:
                st.markdown("**Quarts**")
                for q in qs:
                    st.write(
                        f"Q{q['q']} — {detail['home_club']} {q['home_goals']}.{q['home_behinds']}({q['home_points']})  |  "
                        f"{detail['away_club']} {q['away_goals']}.{q['away_behinds']}({q['away_points']})"
                    )

            pstats = detail.get("player_stats", [])
            if pstats:
                st.markdown("**Stats joueurs (Toulouse)**")
                table = [
                    {"Joueur": ps["player_name"], "Buts": ps["goals"], "Behinds": ps["behinds"], "Points": ps["points"]}
                    for ps in pstats
                ]
                st.dataframe(table, hide_index=True, use_container_width=True)
            else:
                st.info("Aucune stat joueur enregistrée pour ce match.")
        st.markdown("---")
# ---------- FIN ----------