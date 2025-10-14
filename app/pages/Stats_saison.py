# Tops buteurs, moyennes, etc.
# app/pages/3_📊_Stats_saison.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from sqlalchemy import select, func, case, or_
from core.db import get_session, init_db
from core.models import Base, Match, PlayerStat

st.set_page_config(page_title="Stats saison", page_icon="📊")
st.title("📊 Stats saison")

init_db(Base)

season = st.text_input("Saison", value="2025")
club = "Toulouse"
club_lower = club.lower()

# Top buteurs (points total)
with get_session() as s:
    q = (
        select(
            PlayerStat.player_name,
            func.sum(PlayerStat.goals).label("goals"),
            func.sum(PlayerStat.behinds).label("behinds"),
            func.sum(PlayerStat.points).label("points"),
            func.count(PlayerStat.match_id).label("games"),
        )
        .join(Match, Match.id == PlayerStat.match_id)
        .where(Match.season_id == season)
        .group_by(PlayerStat.player_name)
        .order_by(func.sum(PlayerStat.points).desc())
    )
    rows = s.execute(q).all()

if not rows:
    st.info("Aucune donnée pour cette saison.")
else:
    st.subheader("🏆 Classement buteurs (points)")
    table = [
        {
            "Joueur": r.player_name,
            "Buts": int(r.goals or 0),
            "Behinds": int(r.behinds or 0),
            "Points": int(r.points or 0),
            "Moy. pts/match": round((r.points or 0) / max(r.games, 1), 2),
            "Précision (%)": round(100 * (r.goals or 0) / max((r.goals or 0) + (r.behinds or 0), 1), 1),
        }
        for r in rows
    ]
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption(f"{len(rows)} joueurs au total")

    # 📈 Moyennes par match (Toulouse) – calcul correct via CASE
    st.subheader("📈 Moyennes par match (Toulouse)")

    points_for = case(
        (func.lower(Match.home_club) == club_lower, Match.total_home_points),
        else_=Match.total_away_points,
    )
    points_against = case(
        (func.lower(Match.home_club) == club_lower, Match.total_away_points),
        else_=Match.total_home_points,
    )

    with get_session() as s:
        q2 = (
            select(
                func.count(Match.id).label("games"),
                func.coalesce(func.sum(points_for), 0).label("sum_for"),
                func.coalesce(func.sum(points_against), 0).label("sum_against"),
            )
            .where(
                or_(
                    func.lower(Match.home_club) == club_lower,
                    func.lower(Match.away_club) == club_lower,
                ),
                Match.season_id == season,
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
