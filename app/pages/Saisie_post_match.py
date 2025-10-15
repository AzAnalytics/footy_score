# app/pages/1_📝_Saisie_post_match.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from datetime import date
import pandas as pd

# Modèles
from core.models import Match, Quarter, PlayerStat

# Repos & services
from core.repos.players_repo import list_players, upsert_players
from services.match_service import save_post_match

# Règles métier
from core.scoring import sum_quarters_match
from core.validators import validate_match, issues_as_strings, summarize_result

from services.auth_service import require_login, current_user

# UI
from ui.nav import sidebar_menu
from ui.inputs import score_inputs, players_stat_table

u = sidebar_menu()

st.set_page_config(page_title="Saisie post-match", page_icon="📝")
st.title("📝 Saisie post-match")

# -------- Helpers sécurité / contexte ----------
def _auth_ctx() -> dict:
    u = current_user() or {}
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "team_name": (u.get("team_name") or "").strip(),
        "is_admin": bool(u.get("is_admin")),
    }

def _ensure_csrf():
    if "csrf_token" not in st.session_state:
        import secrets
        st.session_state["csrf_token"] = secrets.token_urlsafe(24)
    return st.session_state["csrf_token"]

def _check_csrf(tok: str | None) -> bool:
    return bool(tok and tok == st.session_state.get("csrf_token"))

user = require_login()
caller = _auth_ctx()
csrf = _ensure_csrf()

user_team = caller["team_name"] or "Mon équipe"

# -------- 1) Informations du match ----------
st.subheader("1) Informations du match")
c1, c2 = st.columns(2)
match_date = c1.date_input("Date", value=date.today())
season_id = c2.text_input("Saison", value=str(match_date.year))

c3, c4 = st.columns(2)
home_is_myteam = c3.selectbox(f"{user_team} est…", ["Domicile", "Extérieur"]) == "Domicile"
opponent = (c4.text_input("Adversaire", placeholder="Lyon") or "").strip() or "Adversaire"
venue = st.text_input("Lieu", placeholder="Stade…").strip() or None

home_name = (user_team if home_is_myteam else opponent)
away_name = (opponent if home_is_myteam else user_team)

# -------- 2) Score ----------
st.subheader("2) Score")
use_quarters = st.toggle("Saisir les scores par quart-temps", value=True)

quarters: list[Quarter] = []
total_home = 0
total_away = 0

if use_quarters:
    for qn in range(1, 4 + 1):
        st.markdown(f"**Quart-temps {qn}**")
        h = score_inputs(f"{home_name} (Q{qn})")
        a = score_inputs(f"{away_name} (Q{qn})")
        quarters.append(
            Quarter(
                q=qn,
                home_goals=h["goals"], home_behinds=h["behinds"], home_points=h["points"],
                away_goals=a["goals"], away_behinds=a["behinds"], away_points=a["points"],
            )
        )
    sums = sum_quarters_match(quarters)
    total_home, total_away = sums["home"][2], sums["away"][2]
    st.info(f"Totaux cumulés → **{home_name} {total_home} – {total_away} {away_name}**")
else:
    st.markdown("**Score final uniquement**")
    h = score_inputs(f"{home_name} (Final)")
    a = score_inputs(f"{away_name} (Final)")
    total_home, total_away = h["points"], a["points"]

# -------- 3) Stats joueurs (côté mon équipe) ----------
st.subheader(f"3) Stats joueurs ({user_team})")

# Liste des joueurs existants pour l'équipe de l'utilisateur
try:
    existing_players = [p["name"] for p in list_players(user_ctx=caller)]  # filtré par club via repo
except Exception:
    existing_players = []

default_players = existing_players or [
    "Joueur 1", "Joueur 2", "Joueur 3", "Joueur 4", "Joueur 5", "Joueur 6",
    "Joueur 7", "Joueur 8", "Joueur 9", "Joueur 10", "CSC"
]

rows = players_stat_table(default_players)
team_points = sum(r["points"] for r in rows)
st.info(f"Somme points joueurs {user_team} : **{team_points}**")

notes = st.text_area("Notes (optionnel)")

# -------- 3bis) Construire un objet Match pour valider ----------
tmp_match = Match(
    season_id=season_id.strip(),
    date=match_date,
    venue=venue,
    home_club=home_name,
    away_club=away_name,
    total_home_points=int(total_home),
    total_away_points=int(total_away),
)
tmp_match.quarters = quarters
tmp_match.player_stats = [
    PlayerStat(
        player_id=None,
        player_name=r["player_name"],
        goals=int(r["goals"]),
        behinds=int(r["behinds"]),
        points=int(r["points"]),
    )
    for r in rows
]

# Déterminer le côté de l'équipe de l'utilisateur pour la validation joueurs vs déclaré
team_side = None
if caller["team_name"]:
    if home_name == caller["team_name"]:
        team_side = "home"
    elif away_name == caller["team_name"]:
        team_side = "away"

# -------- 4) Validations centralisées ----------
st.subheader("4) Validation")
ok, errors, warnings = validate_match(tmp_match, team_side=team_side)
for w in warnings:
    st.warning(str(w))
for e in errors:
    st.error(str(e))
st.caption(summarize_result(ok, errors, warnings))

# -------- 5) Enregistrement ----------
# CSRF caché pour le submit
st.text_input("CSRF", value=csrf, type="password", key="csrf_save", label_visibility="collapsed")
save_btn = st.button("💾 Enregistrer le match", type="primary", disabled=not ok)

if save_btn:
    if not _check_csrf(st.session_state.get("csrf_save")):
        st.error("CSRF invalide.")
    else:
        # Upsert des joueurs dans le club de l'utilisateur (fait côté repo avec user_ctx)
        try:
            upsert_players([r["player_name"] for r in rows], user_ctx=caller)
        except Exception as ex:
            st.warning(f"Upsert joueurs: {ex}")

        # Enregistrement via service (qui devra appliquer user_ctx + validations serveur)
        try:
            saved_ok, verrs, new_id = save_post_match(tmp_match, user_ctx=caller, notes=notes or None)
        except TypeError:
            # fallback au cas où save_post_match n'accepte pas notes/user_ctx (ancienne signature)
            saved_ok, verrs, new_id = save_post_match(tmp_match)

        if not saved_ok:
            for e in verrs or []:
                st.error(str(e))
        else:
            st.success(f"Match enregistré ✅  (id: {new_id})")
            st.balloons()
            st.info("Vous pouvez vérifier/modifier le match dans l’onglet Historique.")
            # Réinitialiser le formulaire proprement
            st.session_state.pop("csrf_token", None)
            st.rerun()
# -----------------------------------------------------------
# Fin de la page