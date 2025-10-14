# Script pour insérer les joueurs initiaux
# scripts/seed_players.py
from app.core.db import init_db
from app.core.models import Base, Player
from app.core.db import get_session

def run():
    init_db(Base)
    names = [
        "Lucas","Simon","Léo","Thomas T","Killian","Guillaume",
        "Josh","Flo","Thomas A","Eric","CSC"
    ]
    with get_session() as s:
        for n in names:
            if not s.query(Player).filter_by(name=n, club="toulouse").first():
                s.add(Player(name=n, club="toulouse", active=1))
    print("✅ Joueurs seedés.")

if __name__ == "__main__":
    run()
