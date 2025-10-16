# scripts/seed_players.py
# -*- coding: utf-8 -*-
"""
Script optionnel pour insérer une liste de joueurs initiale dans la base de données.

Usage :
    python -m scripts.seed_players --club "Toulouse"
    python -m scripts.seed_players --club "Lyon" --file roster.csv

Ce script est idempotent (n'insère pas les joueurs déjà existants)
et peut être utilisé pour initialiser ou tester l'application Footy Score.
"""

from __future__ import annotations
import argparse
import csv
import sys
from typing import List

# --- Imports robustes selon ton projet ---
try:
    # si tu exécutes depuis la racine du projet
    from app.core.db import init_db
    from app.core.models import Base
    from app.core.repos.players_repo import upsert_players
except ModuleNotFoundError:
    # fallback si tu exécutes directement depuis /app
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from core.db import init_db
    from core.models import Base
    from core.repos.players_repo import upsert_players


# --- Configuration par défaut ---
DEFAULT_NAMES = [
    "Lucas", "Simon", "Léo", "Thomas T", "Killian",
    "Guillaume", "Josh", "Flo", "Thomas A", "Eric", "CSC",
]


def _dedupe_keep_order(names: List[str]) -> List[str]:
    """Supprime les doublons tout en gardant l’ordre d’origine."""
    seen = set()
    out: List[str] = []
    for n in names:
        k = n.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(n.strip())
    return out


def _load_csv_names(path: str) -> List[str]:
    """Lit une liste de joueurs depuis un CSV (1 colonne, sans en-tête)."""
    names: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        for row in rd:
            if not row:
                continue
            name = (row[0] or "").strip()
            if name:
                names.append(name)
    return _dedupe_keep_order(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed des joueurs dans la base Footy Score.")
    parser.add_argument("--club", default="Toulouse", help="Nom du club (par défaut: Toulouse).")
    parser.add_argument("--file", help="Chemin vers un CSV contenant la liste des joueurs.")
    args = parser.parse_args(argv)

    # Initialisation de la base
    init_db(Base)

    # Chargement des noms
    if args.file:
        try:
            names = _load_csv_names(args.file)
        except Exception as e:
            print(f"❌ Erreur lecture fichier {args.file}: {e}")
            return 1
    else:
        names = DEFAULT_NAMES[:]

    if not names:
        print("ℹ️ Aucun joueur à insérer.")
        return 0

    # Suppression doublons et insertion idempotente
    names = _dedupe_keep_order(names)
    upsert_players(names, club=args.club)

    print(f"✅ {len(names)} joueurs insérés (ou déjà présents) pour le club « {args.club} ».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
