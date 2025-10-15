# app/core/repos/players_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Optional

from sqlalchemy import select, func, or_, update, delete, insert
from sqlalchemy.exc import IntegrityError

from core.db import get_session
from core.models import Player

# ---------------- Helpers ----------------

def _safe_str(x: Optional[str], max_len: int = 120) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s[:max_len] or None

def _to_dict(p: Player) -> Dict:
    return {
        "id": p.id,
        "name": p.name,
        "club": p.club,
        "active": bool(p.active),
    }

def _is_admin(user_ctx: Optional[dict]) -> bool:
    return bool((user_ctx or {}).get("is_admin"))

def _user_team_name(user_ctx: Optional[dict]) -> str:
    return (user_ctx or {}).get("team_name") or ""

def _apply_user_filter(stmt, user_ctx: Optional[dict]):
    """
    Limite aux joueurs du club de l'utilisateur si non-admin.
    Suppose un modèle 'Player.club' (string). Si tu passes à team_id plus tard,
    remplace par Player.team_id == user.team_id.
    """
    if _is_admin(user_ctx):
        return stmt
    team = _user_team_name(user_ctx).strip()
    if not team:
        # Pas d'équipe = pas d'accès
        return stmt.where(False)
    return stmt.where(Player.club == team)

def _authorized_for_player(user_ctx: Optional[dict], p: Player) -> bool:
    if _is_admin(user_ctx):
        return True
    team = _user_team_name(user_ctx).strip()
    return bool(team) and p and p.club == team

# ---------------- CRUD ----------------

def upsert_players(names: List[str], *, user_ctx: Optional[dict] = None) -> int:
    """
    Ajoute les joueurs manquants (actifs) pour le club de l'utilisateur.
    Retourne le nombre de joueurs insérés. Non-admin : club forcé à son équipe.
    """
    clean = [n.strip() for n in (names or []) if n and str(n).strip()]
    if not clean:
        return 0

    with get_session() as s:
        # Détermine le club cible
        if _is_admin(user_ctx):
            # Admins : peuvent insérer pour un club au choix (ex: via nom "Name :: Club")
            # Mais pour éviter les erreurs, on exige que tous les noms soient simples.
            # Gère la variante avancée ailleurs si besoin.
            club = _safe_str(_user_team_name(user_ctx), 80)
        else:
            club = _safe_str(_user_team_name(user_ctx), 80)

        if not club:
            return 0

        inserted = 0
        for name in clean:
            name_norm = _safe_str(name, 80)
            if not name_norm:
                continue

            existing = s.execute(
                select(Player).where(Player.club == club, Player.name == name_norm)
            ).scalar_one_or_none()
            if existing is None:
                s.add(Player(name=name_norm, club=club, active=1))
                inserted += 1
            else:
                # S'il existe mais inactif, on peut le réactiver
                if not bool(existing.active):
                    existing.active = 1
        s.commit()
        return inserted

def list_players(*, user_ctx: Optional[dict] = None) -> List[Dict]:
    """Liste des joueurs ACTIFS du club de l'utilisateur (triés par nom)."""
    with get_session() as s:
        stmt = select(Player).where(Player.active == 1).order_by(Player.name.asc())
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_to_dict(p) for p in res]

def list_all_players(*, user_ctx: Optional[dict] = None) -> List[Dict]:
    """Liste de tous les joueurs (actifs + inactifs) visibles par l'utilisateur."""
    with get_session() as s:
        stmt = select(Player).order_by(Player.name.asc())
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_to_dict(p) for p in res]

def get_player_by_id(player_id: int, *, user_ctx: Optional[dict] = None) -> Optional[Dict]:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p or not _authorized_for_player(user_ctx, p):
            return None
        return _to_dict(p)

def get_player_by_name(name: str, *, user_ctx: Optional[dict] = None) -> Optional[Dict]:
    name = _safe_str(name, 80)
    if not name:
        return None
    with get_session() as s:
        stmt = select(Player).where(Player.name == name).limit(1)
        stmt = _apply_user_filter(stmt, user_ctx)
        p = s.execute(stmt).scalar_one_or_none()
        return _to_dict(p) if p else None

def deactivate_player(player_id: int, *, user_ctx: Optional[dict] = None) -> bool:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p or not _authorized_for_player(user_ctx, p):
            return False
        p.active = 0
        s.add(p)
        s.commit()
        return True

def reactivate_player(player_id: int, *, user_ctx: Optional[dict] = None) -> bool:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p or not _authorized_for_player(user_ctx, p):
            return False
        p.active = 1
        s.add(p)
        s.commit()
        return True

def rename_player(player_id: int, new_name: str, *, user_ctx: Optional[dict] = None) -> bool:
    new_name = _safe_str(new_name, 80)
    if not new_name:
        return False
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p or not _authorized_for_player(user_ctx, p):
            return False
        p.name = new_name
        try:
            s.flush()  # valide l'unicité (ex: contrainte uq (club, name))
            s.commit()
            return True
        except IntegrityError:
            s.rollback()
            return False

def delete_player(player_id: int, *, user_ctx: Optional[dict] = None) -> bool:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p or not _authorized_for_player(user_ctx, p):
            return False
        s.delete(p)
        s.commit()
        return True

# ------------- Compteurs / Recherche ----------------

def count_players(*, user_ctx: Optional[dict] = None) -> int:
    """Nombre de joueurs actifs visibles par l'utilisateur (club filtré)."""
    with get_session() as s:
        inner = select(Player.id).where(Player.active == 1)
        inner = _apply_user_filter(inner, user_ctx).subquery()
        return int(s.execute(select(func.count()).select_from(inner)).scalar() or 0)

def count_all_players(*, user_ctx: Optional[dict] = None) -> int:
    """Nombre total de joueurs visibles (actifs + inactifs) pour l'utilisateur."""
    with get_session() as s:
        inner = _apply_user_filter(select(Player.id), user_ctx).subquery()
        return int(s.execute(select(func.count()).select_from(inner)).scalar() or 0)

def search_players(query: str, *, user_ctx: Optional[dict] = None) -> List[Dict]:
    """Recherche par nom (contient), joueurs actifs uniquement, filtrés par club utilisateur."""
    q = _safe_str(query, 80)
    if not q:
        return []
    with get_session() as s:
        stmt = (
            select(Player)
            .where(Player.active == 1, Player.name.ilike(f"%{q}%"))
            .order_by(Player.name.asc())
        )
        stmt = _apply_user_filter(stmt, user_ctx)
        res = s.execute(stmt).scalars().all()
        return [_to_dict(p) for p in res]
# ---------- FIN ----------
