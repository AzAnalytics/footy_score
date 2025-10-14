# CRUD Matchs
# app/core/repos/matches_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Optional
from datetime import date
from sqlalchemy import select, func, and_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy import select, or_
from core.db import get_session
from core.models import Match, Quarter, PlayerStat


from ..db import get_session
from ..models import Match, Quarter, PlayerStat


# ---------- Helpers (ORM -> dict) ----------
def _quarter_to_dict(q: Quarter) -> Dict:
    return {
        "id": q.id,
        "q": q.q,
        "home_goals": q.home_goals,
        "home_behinds": q.home_behinds,
        "home_points": q.home_points,
        "away_goals": q.away_goals,
        "away_behinds": q.away_behinds,
        "away_points": q.away_points,
    }

def _playerstat_to_dict(ps: PlayerStat) -> Dict:
    return {
        "id": ps.id,
        "match_id": ps.match_id,
        "player_id": ps.player_id,
        "player_name": ps.player_name,
        "goals": ps.goals,
        "behinds": ps.behinds,
        "points": ps.points,
    }

def _match_to_dict(m: Match, with_children: bool = False) -> Dict:
    data = {
        "id": m.id,
        "season_id": m.season_id,
        "date": m.date.isoformat() if hasattr(m.date, "isoformat") else str(m.date),
        "venue": m.venue,
        "home_club": m.home_club,
        "away_club": m.away_club,
        "total_home_points": m.total_home_points,
        "total_away_points": m.total_away_points,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
    if with_children:
        data["quarters"] = [_quarter_to_dict(q) for q in sorted(m.quarters, key=lambda x: x.q)]
        data["player_stats"] = [_playerstat_to_dict(ps) for ps in m.player_stats]
    return data


# ---------- CRUD ----------
def insert_match(match: Match) -> int:
    with get_session() as s:
        s.add(match)
        s.flush()
        return match.id

def get_match(match_id: int) -> Optional[Dict]:
    with get_session() as s:
        m = s.execute(
            select(Match)
            .options(
                selectinload(Match.quarters),
                selectinload(Match.player_stats),
            )
            .where(Match.id == match_id)
        ).scalar_one_or_none()        # pas besoin de .unique()
        return _match_to_dict(m, with_children=True) if m else None
def list_matches(limit: int = 50) -> List[Dict]:
    """Liste des matchs (dict) sans enfants, triés par date desc."""
    with get_session() as s:
        res = s.execute(
            select(Match).order_by(Match.date.desc()).limit(limit)
        ).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def delete_match(match_id: int) -> bool:
    with get_session() as s:
        m = s.get(Match, match_id)
        if not m:
            return False
        s.delete(m)
        return True

def update_match(match_id: int, updated_match: Match) -> bool:
    """Met à jour le match et remplace intégralement quarts & player_stats."""
    with get_session() as s:
        existing = s.get(Match, match_id)
        if not existing:
            return False

        # Champs simples
        existing.season_id = updated_match.season_id
        existing.date = updated_match.date
        existing.venue = updated_match.venue
        existing.home_club = updated_match.home_club
        existing.away_club = updated_match.away_club
        existing.total_home_points = updated_match.total_home_points
        existing.total_away_points = updated_match.total_away_points

        # Remplace les quarts
        existing.quarters.clear()
        for q in updated_match.quarters:
            existing.quarters.append(Quarter(
                q=q.q,
                home_goals=q.home_goals,
                home_behinds=q.home_behinds,
                home_points=q.home_points,
                away_goals=q.away_goals,
                away_behinds=q.away_behinds,
                away_points=q.away_points,
            ))

        # Remplace les stats joueurs
        existing.player_stats.clear()
        for ps in updated_match.player_stats:
            existing.player_stats.append(PlayerStat(
                player_id=ps.player_id,
                player_name=ps.player_name,
                goals=ps.goals,
                behinds=ps.behinds,
                points=ps.points,
            ))
        return True


# ---------- Comptages / Listes / Sélections ----------
def count_matches() -> int:
    with get_session() as s:
        return int(s.execute(select(func.count(Match.id))).scalar() or 0)

def list_matches_by_season(season_id: str) -> List[Dict]:
    with get_session() as s:
        res = s.execute(
            select(Match)
            .where(Match.season_id == season_id)
            .order_by(Match.date.desc())
        ).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def list_all_seasons() -> List[str]:
    with get_session() as s:
        rows = s.execute(
            select(Match.season_id).distinct().order_by(Match.season_id.desc())
        ).all()
        return [r[0] for r in rows]

def get_latest_match() -> Optional[Dict]:
    with get_session() as s:
        m = s.execute(
            select(Match).order_by(Match.date.desc()).limit(1)
        ).scalar_one_or_none()
        return _match_to_dict(m, with_children=False) if m else None

def get_earliest_match() -> Optional[Dict]:
    with get_session() as s:
        m = s.execute(
            select(Match).order_by(Match.date.asc()).limit(1)
        ).scalar_one_or_none()
        return _match_to_dict(m, with_children=False) if m else None

def get_matches_in_date_range(start_date: date, end_date: date) -> List[Dict]:
    with get_session() as s:
        res = s.execute(
            select(Match)
            .where(and_(Match.date >= start_date, Match.date <= end_date))
            .order_by(Match.date.desc())
        ).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def get_matches_for_player(player_id: int) -> List[Dict]:
    with get_session() as s:
        res = s.execute(
            select(Match)
            .join(PlayerStat, Match.id == PlayerStat.match_id)
            .where(PlayerStat.player_id == player_id)
            .order_by(Match.date.desc())
        ).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def get_matches_for_player_in_season(player_id: int, season_id: str) -> List[Dict]:
    with get_session() as s:
        res = s.execute(
            select(Match)
            .join(PlayerStat, Match.id == PlayerStat.match_id)
            .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
            .order_by(Match.date.desc())
        ).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]


# ---------- Agrégations (SUM) ----------
def get_total_goals_for_player(player_id: int) -> int:
    with get_session() as s:
        return int(
            s.execute(select(func.coalesce(func.sum(PlayerStat.goals), 0))
                      .where(PlayerStat.player_id == player_id)).scalar() or 0
        )

def get_total_behinds_for_player(player_id: int) -> int:
    with get_session() as s:
        return int(
            s.execute(select(func.coalesce(func.sum(PlayerStat.behinds), 0))
                      .where(PlayerStat.player_id == player_id)).scalar() or 0
        )

def get_total_points_for_player(player_id: int) -> int:
    with get_session() as s:
        return int(
            s.execute(select(func.coalesce(func.sum(PlayerStat.points), 0))
                      .where(PlayerStat.player_id == player_id)).scalar() or 0
        )

def get_total_goals_for_player_in_season(player_id: int, season_id: str) -> int:
    with get_session() as s:
        return int(
            s.execute(
                select(func.coalesce(func.sum(PlayerStat.goals), 0))
                .join(Match, PlayerStat.match_id == Match.id)
                .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
            ).scalar() or 0
        )

def get_total_behinds_for_player_in_season(player_id: int, season_id: str) -> int:
    with get_session() as s:
        return int(
            s.execute(
                select(func.coalesce(func.sum(PlayerStat.behinds), 0))
                .join(Match, PlayerStat.match_id == Match.id)
                .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
            ).scalar() or 0
        )

def get_total_points_for_player_in_season(player_id: int, season_id: str) -> int:
    with get_session() as s:
        return int(
            s.execute(
                select(func.coalesce(func.sum(PlayerStat.points), 0))
                .join(Match, PlayerStat.match_id == Match.id)
                .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
            ).scalar() or 0
        )


# ---------- Détails enfants ----------
def get_player_stats_in_match(match_id: int) -> List[Dict]:
    with get_session() as s:
        res = s.execute(
            select(PlayerStat)
            .where(PlayerStat.match_id == match_id)
            .order_by(PlayerStat.player_name.asc())
        ).scalars().all()
        return [_playerstat_to_dict(ps) for ps in res]

def get_quarters_in_match(match_id: int) -> List[Dict]:
    with get_session() as s:
        res = s.execute(
            select(Quarter)
            .where(Quarter.match_id == match_id)
            .order_by(Quarter.q.asc())
        ).scalars().all()
        return [_quarter_to_dict(q) for q in res]


# ---------- Compteurs ----------
def count_matches_in_season(season_id: str) -> int:
    with get_session() as s:
        return int(
            s.execute(
                select(func.count(Match.id)).where(Match.season_id == season_id)
            ).scalar() or 0
        )

def count_all_matches() -> int:
    with get_session() as s:
        return int(s.execute(select(func.count(Match.id))).scalar() or 0)


# ---------- Suppressions ----------
def delete_all_matches() -> int:
    with get_session() as s:
        result = s.execute(delete(Match))
        # SQLAlchemy 2 retourne rowcount ou None selon backend
        return int(result.rowcount or 0)

# --- AJOUT ---


def list_matches_for_team(team_name: str, limit: int = 100):
    """
    Retourne les derniers matchs où l'équipe apparaît en home_club ou away_club.
    """
    team = (team_name or "").strip()
    if not team:
        return []  # ou fallback list_matches(limit)

    with get_session() as s:
        q = (
            select(Match)
            .where(or_(Match.home_club == team, Match.away_club == team))
            .order_by(Match.date.desc(), Match.id.desc())
            .limit(limit)
        )
        rows = s.scalars(q).all()

        # Serialisation dict minimal, cohérente avec ton list_matches() actuel
        out = []
        for m in rows:
            out.append({
                "id": m.id,
                "date": m.date,
                "season_id": m.season_id,
                "home_club": m.home_club,
                "away_club": m.away_club,
                "venue": m.venue,
                "total_home_points": m.total_home_points,
                "total_away_points": m.total_away_points,
                # optionnels si présents dans le modèle
                "total_home_goals": getattr(m, "total_home_goals", None),
                "total_home_behinds": getattr(m, "total_home_behinds", None),
                "total_away_goals": getattr(m, "total_away_goals", None),
                "total_away_behinds": getattr(m, "total_away_behinds", None),
            })
        return out