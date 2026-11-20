import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import os

# Configuration de la page (plein écran, sans marges)
st.set_page_config(page_title="Jumeau Numérique 3D - Rabat", layout="wide", initial_sidebar_state="expanded")

# --- BARRE LATÉRALE SIMPLIFIÉE ---
st.sidebar.title("Affichage")
st.sidebar.markdown("---")

# On garde juste le choix du scénario (pour l'instant, un seul dispo)
scenario = st.sidebar.selectbox("Scénario", ["actuel"], help="Les scénarios simulés seront ajoutés ici.")

# On garde le mode comparaison (qui activera la vue côte à côte plus tard)
compare_mode = st.sidebar.checkbox("Mode comparaison (actuel vs simulé)", False)

st.sidebar.markdown("---")
st.sidebar.caption("Données simulées (SUMO) — Transformation Digitale")

# --- AFFICHAGE PRINCIPAL ---
# On lit le fichier HTML
html_file = Path(__file__).parent / "test_fluide.html"

if html_file.exists():
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # On l'affiche en plein écran (height=800 pour prendre toute la place)
    components.html(html_content, height=800, scrolling=False)
else:
    st.error("Le fichier test_fluide.html est introuvable. Assure-toi qu'il est dans le même dossier que app.py.")

# --- LE BOUTON POUR CESIUM ---
st.sidebar.markdown("---")
st.sidebar.info("💡 **Vue 3D Immersive (Cesium)**\n\nPour voir le rendu réaliste, ouvre le fichier `test_cesium.html` dans un nouvel onglet de ton navigateur.")