# app/ui/layout.py
import streamlit as st

def hide_builtin_sidebar_nav() -> None:
    st.markdown("""
    <style>
    div[data-testid="stSidebarNav"] { display: none !important; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: .5rem; }
    </style>
    """, unsafe_allow_html=True)
