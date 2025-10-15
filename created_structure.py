"""from pathlib import Path

# 📁 Point de départ : ton dossier actuel (footy_score)
base = Path.cwd()

structure = {
    ".env.example": "",
    "requirements.txt": "",
    "app/main.py": "# Entrée Streamlit (menu, routing)\n",
    "app/pages/Saisie_post_match.py": "# Formulaire post-match\n",
    "app/pages/Historique.py": "# Liste des matchs + détails\n",
    "app/pages/Stats_saison.py": "# Tops buteurs, moyennes, etc.\n",
    "app/core/config.py": "# Chargement .env\n",
    "app/core/db.py": "# Connexion Mongo (cache Streamlit)\n",
    "app/core/scoring.py": "# 6*buts + behinds, agrégations\n",
    "app/core/validators.py": "# Règles de cohérence (points, quart-temps…)\n",
    "app/core/models.py": "# Schémas Pydantic (Match, Player, Quarter…)\n",
    "app/core/repos/players_repo.py": "# CRUD Joueurs\n",
    "app/core/repos/matches_repo.py": "# CRUD Matchs\n",
    "app/services/match_service.py": "# Orchestration saisie → validation → save\n",
    "app/services/export_service.py": "# (optionnel) Export PDF/CSV\n",
    "app/ui/inputs.py": "# Petits composants (inputs joueurs, score)\n",
    "app/ui/tables.py": "# Tables/metrics réutilisables\n",
    "scripts/seed_players.py": "# Script pour insérer les joueurs initiaux\n",
}

for rel_path, content in structure.items():
    file_path = base / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        file_path.write_text(content, encoding="utf-8")
        print(f"✅ Créé : {file_path.relative_to(base)}")
    else:
        print(f"⏭️  Déjà présent : {file_path.relative_to(base)}")

print("\nArborescence de base initialisée avec succès 🎉")"""
