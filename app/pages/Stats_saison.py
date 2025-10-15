# app/pages/3_📊_Stats_saison.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from sqlalchemy import select, func, case, or_
from core.db import get_session
from core.models import Match, PlayerStat
from services.auth_service import require_login, current_user

from ui.nav import sidebar_menu
u = sidebar_menu()

st.set_page_config(page_title="Stats saison", page_icon="📊")
st.title("📊 Stats saison")

# ---------------------------
# Helpers / contexte
# ---------------------------
def _auth_ctx() -> dict:
    u = current_user() or {}
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "team_name": (u.get("team_name") or "").strip(),
        "is_admin": bool(u.get("is_admin")),
    }

caller = _auth_ctx()
require_login()  # stop() si non connecté

# ---------------------------
# Filtres (saison, équipe)
# ---------------------------
# Saisons disponibles (depuis la DB)
with get_session(readonly=True) as s:
    seasons = [r[0] for r in s.execute(
        select(Match.season_id).distinct().order_by(Match.season_id.desc())
    ).all()]

default_season = seasons[0] if seasons else str(st.session_state.get("default_season", "")) or ""
season = st.selectbox("Saison", seasons or [default_season] or ["—"], index=0 if seasons else 0)

# Équipe : non-admin = imposé, admin = sélection libre à partir des clubs présents
if caller["is_admin"]:
    with get_session(readonly=True) as s:
        clubs = [r[0] for r in s.execute(
            select(Match.home_club).distinct().order_by(Match.home_club.asc())
        ).all()]
    club = st.selectbox("Équipe", clubs or [caller["team_name"] or "—"], index=0 if clubs else 0)
else:
    if not caller["team_name"]:
        st.info("Aucune équipe n'est associée à votre compte : statistiques globales indisponibles.")
        st.stop()
    club = caller["team_name"]

club_lower = (club or "").lower()

st.markdown("---")

# ---------------------------
# Top buteurs (basé sur PlayerStat)
# NB: PlayerStat contient les stats de l'équipe suivie dans chaque match.
# On filtre donc par matchs où `club` apparaît (domicile ou extérieur) + saison.
# ---------------------------
with get_session(readonly=True) as s:
    q = (
        select(
            PlayerStat.player_name.label("player_name"),
            func.coalesce(func.sum(PlayerStat.goals), 0).label("goals"),
            func.coalesce(func.sum(PlayerStat.behinds), 0).label("behinds"),
            func.coalesce(func.sum(PlayerStat.points), 0).label("points"),
            func.count(func.distinct(PlayerStat.match_id)).label("games"),
        )
        .join(Match, Match.id == PlayerStat.match_id)
        .where(
            Match.season_id == season,
            or_(
                func.lower(Match.home_club) == club_lower,
                func.lower(Match.away_club) == club_lower,
            ),
        )
        .group_by(PlayerStat.player_name)
        .order_by(func.coalesce(func.sum(PlayerStat.points), 0).desc(), PlayerStat.player_name.asc())
    )
    rows = s.execute(q).all()

if not rows:
    st.info("Aucune donnée pour cette saison/équipe.")
    st.stop()

st.subheader("🏆 Classement buteurs (points)")
table = [
    {
        "Joueur": r.player_name,
        "Buts": int(r.goals or 0),
        "Behinds": int(r.behinds or 0),
        "Points": int(r.points or 0),
        "Moy. pts/match": round((int(r.points or 0)) / max(int(r.games or 0), 1), 2),
        "Précision (%)": round(100 * int(r.goals or 0) / max(int(r.goals or 0) + int(r.behinds or 0), 1), 1),
        "Matches": int(r.games or 0),
    }
    for r in rows
]
st.dataframe(table, hide_index=True, use_container_width=True)
st.caption(f"{len(rows)} joueurs au total")

# Export CSV
import pandas as pd
df = pd.DataFrame(table)
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Export buteurs (CSV)", data=csv_bytes, file_name=f"buteurs_{club}_{season}.csv", mime="text/csv")

st.markdown("---")

# ---------------------------
# 📈 Moyennes par match (équipe sélectionnée)
# ---------------------------
st.subheader(f"📈 Moyennes par match ({club})")

points_for = case(
    (func.lower(Match.home_club) == club_lower, Match.total_home_points),
    else_=Match.total_away_points,
)
points_against = case(
    (func.lower(Match.home_club) == club_lower, Match.total_away_points),
    else_=Match.total_home_points,
)

with get_session(readonly=True) as s:
    q2 = (
        select(
            func.count(Match.id).label("games"),
            func.coalesce(func.sum(points_for), 0).label("sum_for"),
            func.coalesce(func.sum(points_against), 0).label("sum_against"),
        )
        .where(
            Match.season_id == season,
            or_(
                func.lower(Match.home_club) == club_lower,
                func.lower(Match.away_club) == club_lower,
            ),
        )
    )
    r2 = s.execute(q2).one()

games = int(r2.games or 0)
sum_for = int(r2.sum_for or 0)
sum_against = int(r2.sum_against or 0)
avg_for = round(sum_for / games, 2) if games else 0.0
avg_against = round(sum_against / games, 2) if games else 0.0

st.write(f"- Nombre de matchs joués : **{games}**")
st.write(f"- Moyenne points marqués par match : **{avg_for}**")
st.write(f"- Moyenne points encaissés par match : **{avg_against}**")
st.caption(f"Totaux saison — Pour: {sum_for} • Contre: {sum_against} • Diff: {sum_for - sum_against:+}")
st.markdown("---")
# ---------------------------