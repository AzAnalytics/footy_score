# app/core/config.py
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH, override=True)

# Environnement
ENV = os.getenv("ENV", "local").lower()

# Base SQL (SQLite local par défaut)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///footy_local.db")

# App
CLUB_ID = os.getenv("CLUB_ID", "toulouse")
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
STREAMLIT_ADDRESS = os.getenv("STREAMLIT_ADDRESS", "localhost")
EXPORT_PATH = os.getenv("EXPORT_PATH", "exports/")

def print_config_summary():
    print("=== ⚙️ CONFIG FOOTY SCORE (SQL local) ===")
    print(f"ENV ..............: {ENV}")
    print(f"DATABASE_URL .....: {DATABASE_URL}")
    print(f"CLUB_ID ..........: {CLUB_ID}")
    print("=========================================")

if __name__ == "__main__":
    print_config_summary()
