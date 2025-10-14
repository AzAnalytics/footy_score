# Schémas Pydantic (Match, Player, Quarter…)
# app/core/models.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    club = Column(String, nullable=False, default="toulouse")
    active = Column(Integer, nullable=False, default=1)  # 1 actif, 0 inactif

    __table_args__ = (UniqueConstraint("club", "name", name="uq_player_club_name"),)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    season_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    venue = Column(String, nullable=True)
    home_club = Column(String, nullable=False)
    away_club = Column(String, nullable=False)
    total_home_points = Column(Integer, nullable=False, default=0)
    total_away_points = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    quarters = relationship("Quarter", cascade="all, delete-orphan", back_populates="match")
    player_stats = relationship("PlayerStat", cascade="all, delete-orphan", back_populates="match")

class Quarter(Base):
    __tablename__ = "quarters"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    q = Column(Integer, nullable=False)
    home_goals = Column(Integer, nullable=False, default=0)
    home_behinds = Column(Integer, nullable=False, default=0)
    home_points = Column(Integer, nullable=False, default=0)
    away_goals = Column(Integer, nullable=False, default=0)
    away_behinds = Column(Integer, nullable=False, default=0)
    away_points = Column(Integer, nullable=False, default=0)

    match = relationship("Match", back_populates="quarters")

class PlayerStat(Base):
    __tablename__ = "player_stats"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    player_name = Column(String, nullable=False)   # sécurité si joueur sans ID
    goals = Column(Integer, nullable=False, default=0)
    behinds = Column(Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)

    match = relationship("Match", back_populates="player_stats")
    player = relationship("Player")

# Helpers métier
def calc_points(goals: int, behinds: int) -> int:
    return 6 * goals + behinds
