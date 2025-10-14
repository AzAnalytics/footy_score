# app/core/db.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


from .config import DATABASE_URL

# SQLite: pour multi-threads avec Streamlit
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

@contextmanager
def get_session() -> Generator:
    """Contexte de session SQLAlchemy."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_db(Base) -> None:
    """Crée les tables si absentes."""
    Base.metadata.create_all(bind=engine)


def connection_info() -> str:
    try:
        with get_session() as s:
            s.execute(text("SELECT 1"))
        return "✅ SQLite connecté"
    except Exception as e:
        return f"❌ Erreur SQLite: {e}"


if __name__ == "__main__":
    print(connection_info())
