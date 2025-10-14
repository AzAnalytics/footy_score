# app/core/repos/players_repo.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Optional

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from ..db import get_session
from ..models import Player


# ---------- Helpers ----------
def _to_dict(p: Player) -> Dict:
    return {"id": p.id, "name": p.name, "club": p.club, "active": bool(p.active)}


# ---------- CRUD ----------
def upsert_players(names: List[str], club: str = "toulouse") -> None:
    """Ajoute les joueurs manquants (actifs) ; ignore les existants."""
    clean = [n.strip() for n in names if n and n.strip()]
    if not clean:
        return
    with get_session() as s:
        for name in clean:
            existing = s.execute(
                select(Player).where(Player.club == club, Player.name == name)
            ).scalar_one_or_none()
            if existing is None:
                s.add(Player(name=name, club=club, active=1))


def list_players(club: str = "toulouse") -> List[Dict]:
    """Liste des joueurs actifs du club (triés par nom)."""
    with get_session() as s:
        res = s.execute(
            select(Player).where(Player.club == club, Player.active == 1).order_by(Player.name.asc())
        )
        return [_to_dict(p) for p in res.scalars().all()]


def list_all_players(club: str = "toulouse") -> List[Dict]:
    """Liste de tous les joueurs (actifs + inactifs)."""
    with get_session() as s:
        res = s.execute(
            select(Player).where(Player.club == club).order_by(Player.name.asc())
        )
        return [_to_dict(p) for p in res.scalars().all()]


def get_player_by_id(player_id: int) -> Optional[Dict]:
    with get_session() as s:
        p = s.get(Player, player_id)
        return _to_dict(p) if p else None


def get_player_by_name(name: str, club: str = "toulouse") -> Optional[Dict]:
    with get_session() as s:
        p = s.execute(
            select(Player).where(Player.club == club, Player.name == name)
        ).scalar_one_or_none()
        return _to_dict(p) if p else None


def deactivate_player(player_id: int) -> bool:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p:
            return False
        p.active = 0
        return True


def reactivate_player(player_id: int) -> bool:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p:
            return False
        p.active = 1
        return True


def rename_player(player_id: int, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p:
            return False
        p.name = new_name
        try:
            s.flush()  # vérifie l'unicité (uq_player_club_name) avant commit
            return True
        except IntegrityError:
            s.rollback()
            return False


def delete_player(player_id: int) -> bool:
    with get_session() as s:
        p = s.get(Player, player_id)
        if not p:
            return False
        s.delete(p)
        return True


# ---------- Compteurs / Recherche ----------
def count_players(club: str = "toulouse") -> int:
    """Nombre de joueurs actifs du club."""
    with get_session() as s:
        return int(
            s.execute(
                select(func.count()).select_from(
                    select(Player.id).where(Player.club == club, Player.active == 1).subquery()
                )
            ).scalar() or 0
        )


def count_all_players(club: str = "toulouse") -> int:
    """Nombre total de joueurs du club (actifs + inactifs)."""
    with get_session() as s:
        return int(
            s.execute(
                select(func.count()).select_from(
                    select(Player.id).where(Player.club == club).subquery()
                )
            ).scalar() or 0
        )


def search_players(query: str, club: str = "toulouse") -> List[Dict]:
    """Recherche par nom (contient), joueurs actifs uniquement."""
    q = (query or "").strip()
    if not q:
        return []
    with get_session() as s:
        res = s.execute(
            select(Player).where(
                Player.club == club,
                Player.active == 1,
                Player.name.ilike(f"%{q}%"),  # OK sur SQLite (LIKE insensible ASCII)
            ).order_by(Player.name.asc())
        )
        return [_to_dict(p) for p in res.scalars().all()]
# ---------- FIN ----------