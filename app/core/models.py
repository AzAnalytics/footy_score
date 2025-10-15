# app/core/models.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Boolean,
    UniqueConstraint, CheckConstraint, Index, func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# -----------------------------------------------------------------------------
# Helpers métier
# -----------------------------------------------------------------------------
def calc_points(goals: int, behinds: int) -> int:
    return int(goals) * 6 + int(behinds)

# -----------------------------------------------------------------------------
# Player
# -----------------------------------------------------------------------------
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)                  # borne raisonnable
    club = Column(String(80), nullable=False, default="toulouse")
    active = Column(Boolean, nullable=False, default=True)     # bool natif

    __table_args__ = (
        UniqueConstraint("club", "name", name="uq_player_club_name"),
        CheckConstraint("length(name) > 0", name="ck_player_name_not_empty"),
        CheckConstraint("length(club) > 0", name="ck_player_club_not_empty"),
        Index("ix_player_club_active_name", "club", "active", "name"),
        Index("ix_player_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Player id={self.id} {self.club}:{self.name} active={self.active}>"

# -----------------------------------------------------------------------------
# Match
# -----------------------------------------------------------------------------
class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    season_id = Column(String(16), nullable=False)
    date = Column(Date, nullable=False)
    venue = Column(String(120), nullable=True)
    home_club = Column(String(80), nullable=False)
    away_club = Column(String(80), nullable=False)
    total_home_points = Column(Integer, nullable=False, default=0)
    total_away_points = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    quarters = relationship(
        "Quarter",
        cascade="all, delete-orphan",
        back_populates="match",
        lazy="selectin",
    )
    player_stats = relationship(
        "PlayerStat",
        cascade="all, delete-orphan",
        back_populates="match",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("length(season_id) > 0", name="ck_match_season_not_empty"),
        CheckConstraint("length(home_club) > 0", name="ck_match_home_not_empty"),
        CheckConstraint("length(away_club) > 0", name="ck_match_away_not_empty"),
        CheckConstraint("total_home_points >= 0", name="ck_match_home_points_nonneg"),
        CheckConstraint("total_away_points >= 0", name="ck_match_away_points_nonneg"),
        Index("ix_match_date", "date"),
        Index("ix_match_season", "season_id"),
        Index("ix_match_home", "home_club"),
        Index("ix_match_away", "away_club"),
    )

    def __repr__(self) -> str:
        return f"<Match id={self.id} {self.home_club} vs {self.away_club} on {self.date}>"

# -----------------------------------------------------------------------------
# Quarter
# -----------------------------------------------------------------------------
class Quarter(Base):
    __tablename__ = "quarters"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    q = Column(Integer, nullable=False)  # 1..4 (ou 1..x si format réduit)
    home_goals = Column(Integer, nullable=False, default=0)
    home_behinds = Column(Integer, nullable=False, default=0)
    home_points = Column(Integer, nullable=False, default=0)
    away_goals = Column(Integer, nullable=False, default=0)
    away_behinds = Column(Integer, nullable=False, default=0)
    away_points = Column(Integer, nullable=False, default=0)

    match = relationship("Match", back_populates="quarters", lazy="joined")

    __table_args__ = (
        UniqueConstraint("match_id", "q", name="uq_quarter_match_q"),
        CheckConstraint("q >= 0", name="ck_quarter_q_nonneg"),
        CheckConstraint("home_goals >= 0 AND home_behinds >= 0 AND home_points >= 0", name="ck_quarter_home_nonneg"),
        CheckConstraint("away_goals >= 0 AND away_behinds >= 0 AND away_points >= 0", name="ck_quarter_away_nonneg"),
        Index("ix_quarter_match", "match_id"),
    )

    def __repr__(self) -> str:
        return f"<Quarter match={self.match_id} q={self.q}>"

# -----------------------------------------------------------------------------
# PlayerStat
# -----------------------------------------------------------------------------
class PlayerStat(Base):
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    player_name = Column(String(80), nullable=False)   # fallback si player_id est None
    goals = Column(Integer, nullable=False, default=0)
    behinds = Column(Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)

    match = relationship("Match", back_populates="player_stats", lazy="joined")
    player = relationship("Player", lazy="joined")

    __table_args__ = (
        # Unicité logique: un joueur (id connu) ne doit apparaître qu'une fois par match.
        # Si player_id est NULL, on se rabat sur (match_id, player_name).
        # NB: Les NULL dans les uniques se comportent différemment selon SGBD;
        # cette combinaison évite la plupart des doublons usuels.
        UniqueConstraint("match_id", "player_id", name="uq_stat_match_playerid"),
        UniqueConstraint("match_id", "player_name", name="uq_stat_match_playername"),
        CheckConstraint("goals >= 0 AND behinds >= 0 AND points >= 0", name="ck_stat_nonneg"),
        Index("ix_stat_match", "match_id"),
        Index("ix_stat_player", "player_id"),
    )

    def __repr__(self) -> str:
        return f"<PlayerStat match={self.match_id} player={self.player_id or self.player_name}>"

# -----------------------------------------------------------------------------
# User
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(190), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    team_name = Column(String(120), nullable=True)  # ex: "Toulouse" ou "Lyon"
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("length(email) > 0", name="ck_user_email_not_empty"),
        Index("ix_user_team", "team_name"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} admin={self.is_admin}>"

# -----------------------------------------------------------------------------
# Audit
# -----------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_email = Column(String(190), nullable=False)
    action = Column(String(120), nullable=False)
    target_type = Column(String(60), nullable=False)
    target_id = Column(Integer, nullable=False)
    payload = Column(String(2048), nullable=True)

    __table_args__ = (
        Index("ix_audit_ts", "ts"),
        Index("ix_audit_actor", "actor_email"),
        Index("ix_audit_target", "target_type", "target_id"),
    )

    def __repr__(self) -> str:
        return f"<Audit {self.ts} {self.actor_email} {self.action} {self.target_type}:{self.target_id}>"
# ---------------------------------------------------------------------------