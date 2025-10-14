# Formulaire post-match
# app/pages/1_📝_Saisie_post_match.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from datetime import date

# Modèles & DB
from core.db import init_db
from core.models import Base, Match, Quarter, PlayerStat

# Repos & services
from core.repos.players_repo import list_players, upsert_players
from services.match_service import save_post_match

# ✅ Règles métier centralisées
from core.scoring import (
    sum_quarters_match,
    validate_match_consistency,
    validate_players_vs_declared,
)

# UI
from ui.inputs import score_inputs, players_stat_table

st.set_page_config(page_title="Saisie post-match", page_icon="📝")
st.title("📝 Saisie post-match")

# Init schéma au cas où
init_db(Base)

st.subheader("1) Informations du match")
col1, col2 = st.columns(2)
match_date = col1.date_input("Date", value=date.today())
season_id = col2.text_input("Saison", value=str(match_date.year))
col3, col4 = st.columns(2)
home_is_toulouse = col3.selectbox("Toulouse est…", ["Domicile", "Extérieur"]) == "Domicile"
opponent = col4.text_input("Adversaire", placeholder="Lyon").strip() or "Adversaire"
venue = st.text_input("Lieu", placeholder="Stade…")

home_name = "Toulouse" if home_is_toulouse else opponent
away_name = opponent if home_is_toulouse else "Toulouse"

st.subheader("2) Score")
use_quarters = st.toggle("Saisir les scores par quart-temps", value=True)

quarters = []
total_home = 0
total_away = 0

if use_quarters:
    for qn in range(1, 5):
        st.markdown(f"**Quart-temps {qn}**")
        h = score_inputs(f"{home_name} (Q{qn})")
        a = score_inputs(f"{away_name} (Q{qn})")
        quarters.append(
            Quarter(
                q=qn,
                home_goals=h["goals"],
                home_behinds=h["behinds"],
                home_points=h["points"],
                away_goals=a["goals"],
                away_behinds=a["behinds"],
                away_points=a["points"],
            )
        )
    # ✅ Totaux via scoring (somme des quarts)
    sums = sum_quarters_match(quarters)
    total_home = sums["home"][2]
    total_away = sums["away"][2]
    st.info(f"Totaux cumulés → **{home_name} {total_home} – {total_away} {away_name}**")
else:
    st.markdown("**Score final uniquement**")
    h = score_inputs(f"{home_name} (Final)")
    a = score_inputs(f"{away_name} (Final)")
    total_home, total_away = h["points"], a["points"]

st.subheader("3) Stats joueurs (Toulouse)")
players = [p["name"] for p in list_players("toulouse")] or [
    "Lucas", "Simon", "Léo", "Thomas T", "Killian", "Guillaume", "Josh",
    "Flo", "Thomas A", "Eric", "CSC"
]
rows = players_stat_table(players)
team_points = sum(r["points"] for r in rows)
st.info(f"Somme points joueurs Toulouse : **{team_points}**")

notes = st.text_area("Notes (optionnel)")

# ✅ Construction d'un objet Match *avant* enregistrement pour valider via scoring.py
tmp_match = Match(
    season_id=season_id,
    date=match_date,
    venue=venue or None,
    home_club=home_name,
    away_club=away_name,
    total_home_points=total_home,
    total_away_points=total_away,
)
tmp_match.quarters = quarters
tmp_match.player_stats = [
    PlayerStat(
        player_id=None,
        player_name=r["player_name"],
        goals=r["goals"],
        behinds=r["behinds"],
        points=r["points"],
    )
    for r in rows
]

# ✅ Validations centralisées (cohérences quarts + écart joueurs vs déclaré)
errs = []
errs.extend(validate_match_consistency(tmp_match))
errs.extend(validate_players_vs_declared(tmp_match, toulouse_name="Toulouse"))

st.subheader("4) Enregistrement")
if errs:
    for e in errs:
        st.error(e)

save_btn = st.button("Enregistrer le match", type="primary", disabled=bool(errs))

if save_btn:
    # Upsert éventuel des joueurs
    upsert_players([r["player_name"] for r in rows], club="toulouse")

    # On réutilise tmp_match pour l'enregistrement
    ok, verrs, new_id = save_post_match(tmp_match)
    if not ok:
        for e in verrs:
            st.error(e)
    else:
        st.success(f"Match enregistré ✅  (id: {new_id})")
        st.balloons()
        st.info("Tu peux vérifier/modifier le match dans l'onglet Historique.")
        # Optionnel : afficher le récap
        with st.expander("Voir le récapitulatif du match"):
            # Selon ton modèle, .dict() peut ne pas exister; garde si supporté.
            try:
                st.json(tmp_match.dict(), expanded=False)
            except Exception:
                st.write(tmp_match)

        # Réinitialiser le formulaire
        st.session_state.clear()
        st.experimental_rerun()
        st.markdown("## (formulaire réinitialisé)")
# ---------- FIN ----------