# ⚽ FootyScore

> Application web de suivi des scores de **football australien en France** — saisie des résultats, historique des matchs et statistiques interactives.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B?style=flat&logo=streamlit)
![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?style=flat&logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## 🎯 Objectif

FootyScore répond à un besoin simple : les clubs de football australien en France ne disposent d'aucun outil centralisé pour saisir, consulter et analyser leurs scores. Cette application Streamlit comble ce vide avec une interface légère, intuitive et déployable en local ou sur le web.

---

## 🚀 Fonctionnalités

- **Saisie des scores** — Enregistrement des résultats match par match (équipes, score, date, lieu)
- **Historique des matchs** — Consultation et filtrage de tous les résultats passés
- **Statistiques** — Analyses par équipe, saison et tendances de performance
- **Stockage local** — Base de données SQLite embarquée (`footy_local.db`), aucun serveur requis
- **Interface Streamlit** — Navigation fluide, déployable en un clic

---

## 🛠️ Stack technique

| Composant | Technologie |
|---|---|
| Interface | Streamlit |
| Langage | Python 3.10+ |
| Stockage | SQLite (`footy_local.db`) |
| Configuration | `.streamlit/config.toml` |

---

## 📁 Structure du projet

```
footy_score/
├── app/                    # Modules principaux de l'application
├── scripts/                # Scripts utilitaires (init DB, migrations...)
├── .streamlit/             # Configuration Streamlit
├── footy_local.db          # Base de données SQLite locale
├── created_structure.py    # Script de création de la structure
├── requirements.txt        # Dépendances Python
└── __init.py__
```

---

## ⚙️ Installation

```bash
# 1. Cloner le repo
git clone https://github.com/AzAnalytics/footy_score.git
cd footy_score

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows : venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
streamlit run app/main.py
```

L'application est accessible sur `http://localhost:8501`

---

## 👤 Auteur

**Alexis Zueras** — Fondateur [AZ Analytics](http://alexiszueras.fr)  
Data Analyst & BI Consultant Freelance | Power BI · Oracle SQL · Python · Streamlit

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Alexis_Zueras-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/alexis-zueras)
[![Linktree](https://img.shields.io/badge/Linktree-DataKnightAZFrance-39e09b?style=flat&logo=linktree)](https://linktr.ee/DataKnightAZFrance)
