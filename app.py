import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="Immo Map", layout="wide")
st.title("🗺️ Carte Interactive Immo")


# --- 1. CHARGEMENT ET CALCUL UNIQUE (C'est ici que ça se joue) ---
@st.cache_data
def load_and_prepare_data(csv_path):
    # Lecture
    try:
        df = pd.read_csv(csv_path)
    except:
        df = pd.read_csv(csv_path, sep=';')

    # Nettoyage
    df = df.dropna(subset=['latitude', 'longitude'])

    # --- LA CORRECTION EST ICI ---
    # On calcule le décalage (jitter) UNE SEULE FOIS ici.
    # Le résultat est mis en cache, donc les points ne bougeront plus
    # tant qu'on ne vide pas le cache manuellement.

    def get_jitter(val):
        return val + random.uniform(-0.005, 0.005)

    # On crée directement les colonnes définitives pour la visualisation
    df['lat_viz'] = df['latitude'].apply(get_jitter)
    df['lon_viz'] = df['longitude'].apply(get_jitter)

    return df


FILE_NAME = "immo_gps2.csv"

try:
    df = load_and_prepare_data(FILE_NAME)
except FileNotFoundError:
    st.error(f"Fichier '{FILE_NAME}' introuvable.")
    st.stop()

# --- 2. FILTRES ---
st.sidebar.header("🔍 Filtres de recherche")

# --- A. Filtre VILLE (Avec option "Tout sélectionner") ---
villes_disponibles = sorted(df['Ville'].unique())

# 1. Case à cocher pour "Tout sélectionner"
tout_selectionner = st.sidebar.checkbox("✅ Sélectionner toutes les villes", value=True)

# 2. Logique de sélection
if tout_selectionner:
    # Si coché, on prend tout et on désactive le menu pour éviter la confusion
    villes_selectionnees = villes_disponibles
    st.sidebar.multiselect(
        "📍 Villes sélectionnées",
        options=villes_disponibles,
        default=villes_disponibles,
        disabled=True # Le menu est visible mais grisé
    )
else:
    # Si décoché, l'utilisateur choisit manuellement
    villes_selectionnees = st.sidebar.multiselect(
        "📍 Choisir les villes",
        options=villes_disponibles,
        default=[]
    )

#filtre département


#filtre prix
min_price, max_price = int(df['Prix'].min()), int(df['Prix'].max())
prix_range = st.sidebar.slider("Budget (€)", min_price, max_price, (min_price, max_price))

#filtre surface
min_surf, max_surf = int(df['Surface_m2'].min()), int(df['Surface_m2'].max())
surf_range = st.sidebar.slider(
    "📏 Surface (m²)",
    min_surf, max_surf,
    (min_surf, max_surf)
)


df_filtered = df[
    (df['Prix'] >= prix_range[0]) &
    (df['Prix'] <= prix_range[1])&
    (df['Surface_m2'] >= surf_range[0]) &
    (df['Surface_m2'] <= surf_range[1])&
    (df['Ville'].isin(villes_selectionnees))
]

# Affichage des stats
col1, col2 = st.columns(2)
col1.metric("Biens trouvés", len(df_filtered))
prix_moyen = int(df_filtered['Prix'].mean()) if not df_filtered.empty else 0
col2.metric("Prix moyen", f"{prix_moyen:,} €".replace(',', ' '))

# --- 3. CARTE ---
# Centrage
if not df_filtered.empty:
    center = [df_filtered['lat_viz'].mean(), df_filtered['lon_viz'].mean()]
else:
    center = [46.6, 1.8]

m = folium.Map(location=center, zoom_start=6)

for _, row in df_filtered.iterrows():
    # Contenu HTML
    prix_str = f"{int(row['Prix']):,} €".replace(',', ' ')
    surf_str = f"{int(row['Surface_m2'])} m²"

    tooltip_html = f"<b>{prix_str}</b><br>{surf_str}"

    # On utilise lat_viz et lon_viz qui sont maintenant FIXES
    folium.CircleMarker(
        location=[row['lat_viz'], row['lon_viz']],
        radius=6,
        color="#3186cc",
        fill=True,
        fill_opacity=0.7,
        tooltip=tooltip_html,
        popup=f"{row['Ville']}: {prix_str}"
    ).add_to(m)

# --- 4. AFFICHAGE OPTIMISÉ ---
# returned_objects=[] empêche Streamlit de recharger la page quand tu cliques sur la carte
# cela améliore grandement la stabilité
st_folium(m, width=None, height=600, returned_objects=[])