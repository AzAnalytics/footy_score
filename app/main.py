# app/main.py
# -*- coding: utf-8 -*-
import streamlit as st
from app.core.db import init_db, connection_info
from app.core.models import Base

st.set_page_config(page_title="Toulouse Footy (SQLite)", page_icon="🏉", layout="centered")
st.sidebar.success(connection_info())

init_db(Base)

st.title("🏉 Toulouse Footy – Back-office (SQLite local)")
st.write("Utilise le menu de gauche :")
st.markdown("- 📝 **Saisie post-match**\n- 📚 **Historique**\n- 📊 **Stats saison**")
st.markdown("---")