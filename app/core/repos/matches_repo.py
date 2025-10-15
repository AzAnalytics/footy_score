# CRUD Matchs sécurisés
# app/core/repos/matches_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Optional, Any
from datetime import date as _date

from sqlalchemy import select, func, and_, or_, delete, update
from sqlalchemy.orm import selectinload

from core.db import get_session
from core.models import Match, Quarter, PlayerStat

# --- Utils de sérialisation --------------------------------------------------

def _quarter_to_dict(q: Quarter) -> Dict[str, Any]:
    return {
        "id": q.id,
        "q": int(q.q),
        "home_goals": int(q.home_goals),
        "home_behinds": int(q.home_behinds),
        "home_points": int(q.home_points),
        "away_goals": int(q.away_goals),
        "away_behinds": int(q.away_behinds),
        "away_points": int(q.away_points),
    }

def _playerstat_to_dict(ps: PlayerStat) -> Dict[str, Any]:
    return {
        "id": ps.id,
        "match_id": ps.match_id,
        "player_id": ps.player_id,
        "player_name": ps.player_name,
        "goals": int(ps.goals),
        "behinds": int(ps.behinds),
        "points": int(ps.points),
    }

def _match_to_dict(m: Match, with_children: bool = False) -> Dict[str, Any]:
    data = {
        "id": m.id,
        "season_id": m.season_id,
        "date": m.date.isoformat() if hasattr(m.date, "isoformat") else str(m.date),
        "venue": m.venue,
        "home_club": m.home_club,
        "away_club": m.away_club,
        "total_home_points": int(m.total_home_points or 0),
        "total_away_points": int(m.total_away_points or 0),
        "created_at": m.created_at.isoformat() if getattr(m, "created_at", None) else None,
    }
    if with_children:
        data["quarters"] = [_quarter_to_dict(q) for q in sorted(m.quarters, key=lambda x: x.q or 0)]
        data["player_stats"] = [_playerstat_to_dict(ps) for ps in m.player_stats]
    return data

# --- Sécurité / filtrage ownership ------------------------------------------

def _user_team_name(user_ctx: Optional[dict]) -> str:
    return (user_ctx or {}).get("team_name") or ""

def _is_admin(user_ctx: Optional[dict]) -> bool:
    return bool((user_ctx or {}).get("is_admin"))

def _authorized_for_match(user_ctx: Optional[dict], m: Match) -> bool:
    if _is_admin(user_ctx):
        return True
    team = _user_team_name(user_ctx).strip()
    return bool(team) and team in {m.home_club, m.away_club}

def _apply_user_filter(stmt, user_ctx: Optional[dict]):
    """Filtre SQL par ownership: si non-admin, limite aux matchs de son équipe (home/away)."""
    if _is_admin(user_ctx):
        return stmt
    team = _user_team_name(user_ctx).strip()
    if not team:
        # Pas d'équipe = pas d'accès
        return stmt.where(False)
    return stmt.where(or_(Match.home_club == team, Match.away_club == team))

# --- Aides métier ------------------------------------------------------------

def _safe_str(x: Optional[str], max_len: int = 120) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s[:max_len] or None

def _recompute_match_totals_from_quarters(m: Match) -> None:
    """Optionnel: si tes Quarter sont source de vérité, recalcule les totaux match."""
    if not m.quarters:
        return
    home = sum(int(q.home_points or 0) for q in m.quarters)
    away = sum(int(q.away_points or 0) for q in m.quarters)
    m.total_home_points = home
    m.total_away_points = away

def _recompute_points(goals: int, behinds: int) -> int:
    return int(goals) * 6 + int(behinds)

# --- CRUD --------------------------------------------------------------------

def insert_match(match: Match, *, user_ctx: Optional[dict] = None) -> int:
    """Insère un match. Le caller doit avoir le droit (admin ou club propriétaire)."""
    with get_session() as s:
        # Ownership check minimal: si non admin, l'équipe du user doit figurer au match.
        if not _is_admin(user_ctx):
            team = _user_team_name(user_ctx).strip()
            if not team or team not in {match.home_club, match.away_club}:
                raise PermissionError("Non autorisé à créer ce match pour cette équipe.")

        # Normalisations prudentes
        match.season_id = _safe_str(match.season_id, 16)
        match.venue = _safe_str(match.venue, 120)
        match.home_club = _safe_str(match.home_club, 80)
        match.away_club = _safe_str(match.away_club, 80)

        # Si des quarters sont présents, les totaux match doivent venir des quarters
        _recompute_match_totals_from_quarters(match)

        s.add(match)
        s.flush()   # obtient l'ID
        match_id = match.id
        s.commit()
        # audit(user_ctx, "match.insert", match_id)  # si tu as un repo d'audit
        return match_id

def get_match(match_id: int, *, user_ctx: Optional[dict] = None) -> Optional[Dict]:
    with get_session() as s:
        stmt = (
            select(Match)
            .options(selectinload(Match.quarters), selectinload(Match.player_stats))
            .where(Match.id == match_id)
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        m = s.execute(stmt).scalar_one_or_none()
        return _match_to_dict(m, with_children=True) if m else None

def list_matches(limit: int = 50, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        stmt = select(Match).order_by(Match.date.desc(), Match.id.desc()).limit(int(limit or 50))
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def delete_match(match_id: int, *, user_ctx: Optional[dict] = None) -> bool:
    with get_session() as s:
        m = s.get(Match, match_id)
        if not m:
            return False
        if not _authorized_for_match(user_ctx, m):
            return False
        s.delete(m)
        s.commit()
        # audit(user_ctx, "match.delete", match_id)
        return True

def update_match(match_id: int, updated_match: Match, *, user_ctx: Optional[dict] = None) -> bool:
    """
    Remplace intégralement champs simples + quarters + player_stats.
    Recalcule les points côté serveur.
    """
    with get_session() as s:
        existing = s.get(Match, match_id)
        if not existing:
            return False
        if not _authorized_for_match(user_ctx, existing):
            return False

        # Champs simples (nettoyés)
        existing.season_id = _safe_str(updated_match.season_id, 16)
        existing.date = updated_match.date
        existing.venue = _safe_str(updated_match.venue, 120)
        existing.home_club = _safe_str(updated_match.home_club, 80)
        existing.away_club = _safe_str(updated_match.away_club, 80)

        # Remplace QUARTERS (points déjà calculés dans l'objet ou à recalculer ici si tu stockes goals/behinds)
        existing.quarters.clear()
        for q in updated_match.quarters or []:
            existing.quarters.append(Quarter(
                q=int(q.q or 0),
                home_goals=int(q.home_goals or 0),
                home_behinds=int(q.home_behinds or 0),
                home_points=int(q.home_points or (int(q.home_goals or 0) * 6 + int(q.home_behinds or 0))),
                away_goals=int(q.away_goals or 0),
                away_behinds=int(q.away_behinds or 0),
                away_points=int(q.away_points or (int(q.away_goals or 0) * 6 + int(q.away_behinds or 0))),
            ))

        # Remplace STATS JOUEURS (recalcul points)
        existing.player_stats.clear()
        for ps in updated_match.player_stats or []:
            g = int(ps.goals or 0)
            b = int(ps.behinds or 0)
            existing.player_stats.append(PlayerStat(
                player_id=ps.player_id,
                player_name=_safe_str(ps.player_name, 80) or "Inconnu",
                goals=g,
                behinds=b,
                points=_recompute_points(g, b),
            ))

        # Totaux match depuis quarters (source de vérité)
        _recompute_match_totals_from_quarters(existing)

        s.add(existing)
        s.commit()
        # audit(user_ctx, "match.update", match_id)
        return True

def update_match_fields(
    match_id: int,
    *,
    season_id: Optional[str] = None,
    date: Optional[_date] = None,
    venue: Optional[str] = None,
    home_club: Optional[str] = None,
    away_club: Optional[str] = None,
    total_home_points: Optional[int] = None,
    total_away_points: Optional[int] = None,
    user_ctx: Optional[dict] = None,
) -> bool:
    """Patch partiel. Les totaux sont ignorés si des quarters existent (on privilégie le recalcul)."""
    with get_session() as s:
        m = s.get(Match, match_id)
        if not m:
            return False
        if not _authorized_for_match(user_ctx, m):
            return False

        if season_id is not None:
            m.season_id = _safe_str(season_id, 16)
        if date is not None:
            m.date = date
        if venue is not None:
            m.venue = _safe_str(venue, 120)
        if home_club is not None:
            m.home_club = _safe_str(home_club, 80) or m.home_club
        if away_club is not None:
            m.away_club = _safe_str(away_club, 80) or m.away_club

        if (total_home_points is not None or total_away_points is not None) and not m.quarters:
            # Seulement si pas de quarters (sinon on recalcule depuis quarters)
            if total_home_points is not None:
                m.total_home_points = int(total_home_points)
            if total_away_points is not None:
                m.total_away_points = int(total_away_points)
        else:
            _recompute_match_totals_from_quarters(m)

        s.add(m)
        s.commit()
        # audit(user_ctx, "match.update_fields", match_id)
        return True

# --- Listes / Sélections protégées ------------------------------------------

def count_matches(*, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        stmt = select(func.count(Match.id))
        stmt = _apply_user_filter(stmt, user_ctx)
        return int(s.execute(stmt).scalar() or 0)

def list_matches_by_season(season_id: str, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        season_id = _safe_str(season_id, 16) or ""
        stmt = (
            select(Match)
            .where(Match.season_id == season_id)
            .order_by(Match.date.desc(), Match.id.desc())
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def list_all_seasons(*, user_ctx: Optional[dict] = None) -> List[str]:
    with get_session() as s:
        stmt = select(Match.season_id).distinct().order_by(Match.season_id.desc())
        stmt = _apply_user_filter(stmt, user_ctx)
        rows = s.execute(stmt).all()
        return [r[0] for r in rows]

def get_latest_match(*, user_ctx: Optional[dict] = None) -> Optional[Dict]:
    with get_session() as s:
        stmt = select(Match).order_by(Match.date.desc(), Match.id.desc()).limit(1)
        stmt = _apply_user_filter(stmt, user_ctx)
        m = s.execute(stmt).scalar_one_or_none()
        return _match_to_dict(m, with_children=False) if m else None

def get_earliest_match(*, user_ctx: Optional[dict] = None) -> Optional[Dict]:
    with get_session() as s:
        stmt = select(Match).order_by(Match.date.asc(), Match.id.asc()).limit(1)
        stmt = _apply_user_filter(stmt, user_ctx)
        m = s.execute(stmt).scalar_one_or_none()
        return _match_to_dict(m, with_children=False) if m else None

def get_matches_in_date_range(start_date: _date, end_date: _date, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        stmt = (
            select(Match)
            .where(and_(Match.date >= start_date, Match.date <= end_date))
            .order_by(Match.date.desc(), Match.id.desc())
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def get_matches_for_player(player_id: int, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        stmt = (
            select(Match)
            .join(PlayerStat, Match.id == PlayerStat.match_id)
            .where(PlayerStat.player_id == player_id)
            .order_by(Match.date.desc(), Match.id.desc())
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

def get_matches_for_player_in_season(player_id: int, season_id: str, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        season_id = _safe_str(season_id, 16) or ""
        stmt = (
            select(Match)
            .join(PlayerStat, Match.id == PlayerStat.match_id)
            .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
            .order_by(Match.date.desc(), Match.id.desc())
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

# --- Agrégations protégées ---------------------------------------------------

def get_total_goals_for_player(player_id: int, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        stmt = select(func.coalesce(func.sum(PlayerStat.goals), 0)).join(Match, PlayerStat.match_id == Match.id)
        stmt = _apply_user_filter(stmt, user_ctx).where(PlayerStat.player_id == player_id)
        return int(s.execute(stmt).scalar() or 0)

def get_total_behinds_for_player(player_id: int, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        stmt = select(func.coalesce(func.sum(PlayerStat.behinds), 0)).join(Match, PlayerStat.match_id == Match.id)
        stmt = _apply_user_filter(stmt, user_ctx).where(PlayerStat.player_id == player_id)
        return int(s.execute(stmt).scalar() or 0)

def get_total_points_for_player(player_id: int, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        stmt = select(func.coalesce(func.sum(PlayerStat.points), 0)).join(Match, PlayerStat.match_id == Match.id)
        stmt = _apply_user_filter(stmt, user_ctx).where(PlayerStat.player_id == player_id)
        return int(s.execute(stmt).scalar() or 0)

def get_total_goals_for_player_in_season(player_id: int, season_id: str, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        season_id = _safe_str(season_id, 16) or ""
        stmt = (
            select(func.coalesce(func.sum(PlayerStat.goals), 0))
            .join(Match, PlayerStat.match_id == Match.id)
            .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        return int(s.execute(stmt).scalar() or 0)

def get_total_behinds_for_player_in_season(player_id: int, season_id: str, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        season_id = _safe_str(season_id, 16) or ""
        stmt = (
            select(func.coalesce(func.sum(PlayerStat.behinds), 0))
            .join(Match, PlayerStat.match_id == Match.id)
            .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        return int(s.execute(stmt).scalar() or 0)

def get_total_points_for_player_in_season(player_id: int, season_id: str, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        season_id = _safe_str(season_id, 16) or ""
        stmt = (
            select(func.coalesce(func.sum(PlayerStat.points), 0))
            .join(Match, PlayerStat.match_id == Match.id)
            .where(PlayerStat.player_id == player_id, Match.season_id == season_id)
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        return int(s.execute(stmt).scalar() or 0)

# --- Détails enfants (protégés) ---------------------------------------------

def get_player_stats_in_match(match_id: int, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        # Ownership: vérifier le match
        m = s.get(Match, match_id)
        if not m or not _authorized_for_match(user_ctx, m):
            return []
        res = s.execute(
            select(PlayerStat)
            .where(PlayerStat.match_id == match_id)
            .order_by(PlayerStat.player_name.asc())
        ).scalars().all()
        return [_playerstat_to_dict(ps) for ps in res]

def get_quarters_in_match(match_id: int, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    with get_session() as s:
        m = s.get(Match, match_id)
        if not m or not _authorized_for_match(user_ctx, m):
            return []
        res = s.execute(
            select(Quarter)
            .where(Quarter.match_id == match_id)
            .order_by(Quarter.q.asc())
        ).scalars().all()
        return [_quarter_to_dict(q) for q in res]

# --- Compteurs & suppressions ------------------------------------------------

def count_matches_in_season(season_id: str, *, user_ctx: Optional[dict] = None) -> int:
    with get_session() as s:
        season_id = _safe_str(season_id, 16) or ""
        stmt = select(func.count(Match.id)).where(Match.season_id == season_id)
        stmt = _apply_user_filter(stmt, user_ctx)
        return int(s.execute(stmt).scalar() or 0)

def count_all_matches(*, user_ctx: Optional[dict] = None) -> int:
    # Équivalent à count_matches pour compat
    return count_matches(user_ctx=user_ctx)

def delete_all_matches(*, user_ctx: Optional[dict] = None) -> int:
    """Danger ! Si non-admin, on interdit. Si admin: purge totale."""
    with get_session() as s:
        if not _is_admin(user_ctx):
            return 0
        result = s.execute(delete(Match))
        s.commit()
        return int(result.rowcount or 0)

# --- Sélection par équipe ----------------------------------------------------

def list_matches_for_team(team_name: str, limit: int = 100, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    """
    Derniers matchs où l'équipe apparaît en home/away.
    Si user non-admin, on force son équipe (évite l’énumération d’autres équipes).
    """
    team = _safe_str(team_name, 80)
    if not _is_admin(user_ctx):
        team = _user_team_name(user_ctx).strip() or team
    if not team:
        return []

    with get_session() as s:
        stmt = (
            select(Match)
            .where(or_(Match.home_club == team, Match.away_club == team))
            .order_by(Match.date.desc(), Match.id.desc())
            .limit(int(limit or 100))
        )
        res = s.execute(stmt).scalars().all()
        return [_match_to_dict(m, with_children=False) for m in res]

# --- Remplacement des stats joueurs -----------------------------------------

def replace_player_stats_for_match(
    match_id: int,
    stats_rows: List[Dict[str, Any]],
    *,
    recalc_match_totals_side: Optional[str] = None,  # "home" | "away" | None
    user_ctx: Optional[dict] = None,
) -> bool:
    """
    Remplace TOUTES les PlayerStat du match par la liste fournie.
    Chaque ligne: player_name, goals, behinds. Points recalculés serveur.
    Si recalc_match_totals_side est "home" ou "away", on aligne le total correspondant
    sur la somme des points joueurs fournis.
    """
    with get_session() as s:
        m = s.get(Match, match_id)
        if not m:
            return False
        if not _authorized_for_match(user_ctx, m):
            return False

        # purge anciennes stats
        s.execute(delete(PlayerStat).where(PlayerStat.match_id == match_id))

        # insert des nouvelles + somme
        total_points = 0
        for r in stats_rows or []:
            name = _safe_str((r.get("player_name") or "Inconnu"), 80) or "Inconnu"
            g = int(r.get("goals") or 0)
            b = int(r.get("behinds") or 0)
            p = _recompute_points(g, b)
            total_points += p
            s.add(PlayerStat(
                match_id=match_id,
                player_id=r.get("player_id"),  # peut rester None si non géré
                player_name=name,
                goals=g,
                behinds=b,
                points=p,
            ))

        if recalc_match_totals_side in {"home", "away"}:
            if recalc_match_totals_side == "home":
                m.total_home_points = total_points
            else:
                m.total_away_points = total_points
        else:
            # Par défaut, si tu veux rester cohérent avec les quarters, privilégie les quarters:
            _recompute_match_totals_from_quarters(m)

        s.add(m)
        s.commit()
        # audit(user_ctx, "match.replace_player_stats", match_id)
        return True
# --- Fin Repo Matchs ---------------------------------------------------------