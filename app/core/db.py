# app/core/db.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------------
# Configuration de la base
# -----------------------------------------------------------------------------

# 1) Source de vérité: var d'env, sinon fallback vers config locale
try:
    from .config import DATABASE_URL as _CFG_DATABASE_URL  # optionnel
except Exception:
    _CFG_DATABASE_URL = None

DATABASE_URL = (os.getenv("DATABASE_URL") or _CFG_DATABASE_URL or "sqlite:///./app.db").strip()

# Type de base (sqlite / postgresql / mysql)
URL_LOWER = DATABASE_URL.lower()
IS_SQLITE = URL_LOWER.startswith("sqlite")

# 2) Connexion & pooling
#    - SQLite (fichier ou mémoire) : check_same_thread=False (Streamlit multi-threads)
#    - Autres SGBD : pool raisonnable par défaut + keepalive
connect_args = {}
engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,  # évite les connexions mortes
}

if IS_SQLITE:
    connect_args = {"check_same_thread": False}
    engine_kwargs.update(
        dict(
            connect_args=connect_args,
        )
    )
else:
    # Pool par défaut (ajuste selon hébergeur)
    # - pool_size: nb connexions persistantes
    # - max_overflow: connexions supplémentaires temporaires
    # - pool_recycle: recycle périodiquement (sec) pour éviter "server has gone away"
    # - pool_timeout: délai avant erreur si pool saturé
    engine_kwargs.update(
        dict(
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),  # 30 min
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
        )
    )

engine: Engine = create_engine(DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # évite DetachedInstanceError après commit
    future=True,
)

# -----------------------------------------------------------------------------
# PRAGMA / options spécifiques SQLite
# -----------------------------------------------------------------------------

if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_con, con_record):
        cursor = dbapi_con.cursor()
        # Contraintes FK ON (par défaut OFF en SQLite)
        cursor.execute("PRAGMA foreign_keys=ON;")
        # WAL pour meilleure concurrence lecture/écriture (utile avec Streamlit)
        cursor.execute("PRAGMA journal_mode=WAL;")
        # Équilibre perf/sûreté
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

# -----------------------------------------------------------------------------
# Contexte de session
# -----------------------------------------------------------------------------

@contextmanager
def get_session(*, readonly: bool = False) -> Generator:
    """
    Contexte de session SQLAlchemy.

    - readonly=False (par défaut): commit sur sortie si pas d'exception.
    - readonly=True: rollback forcé sur sortie (aucune écriture persistée).
    """
    session = SessionLocal()
    try:
        yield session
        if readonly:
            session.rollback()  # par principe de précaution
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# -----------------------------------------------------------------------------
# Outils init & santé
# -----------------------------------------------------------------------------

def init_db(Base) -> None:
    """Crée les tables si absentes (usage dev). En prod: préférer Alembic migrations."""
    Base.metadata.create_all(bind=engine)

def connection_info() -> str:
    try:
        with get_session(readonly=True) as s:
            s.execute(text("SELECT 1"))
        if IS_SQLITE:
            return "✅ Base SQLite connectée"
        elif URL_LOWER.startswith("postgresql"):
            return "✅ Base PostgreSQL connectée"
        elif URL_LOWER.startswith(("mysql", "mariadb")):
            return "✅ Base MySQL/MariaDB connectée"
        else:
            return "✅ Base connectée"
    except Exception as e:
        return f"❌ Erreur connexion DB: {e}"

if __name__ == "__main__":
    print(connection_info())
