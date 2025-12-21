import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import random
import hashlib  # ✅ MODIF (jitter déterministe)
import plotly.express as px
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="ImmoViz", layout="wide")

st.title("ImmoBiz")  # <- tu peux changer le nom
st.caption("Données issues de https://www.immobilier.notaires.fr/")

tab_carte, tab_analyses = st.tabs(["🗺️ Carte interactive", "📊 Analyses"])

with tab_carte:
    st.subheader("🗺️ Carte Interactive Immo")
    # --- 1. CHARGEMENT ET CALCUL UNIQUE ---
    @st.cache_data
    def load_and_prepare_data(csv_path):
        # Lecture
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            df = pd.read_csv(csv_path, sep=';')

        # ✅ conversions numériques robustes
        for col in ["Prix", "Surface_m2", "latitude", "longitude"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # ✅ on drop uniquement ce qui est indispensable à la carte
        df = df.dropna(subset=['latitude', 'longitude', 'Prix'])

        # ✅ CORRECTION LOGIQUE : on NE supprime PAS les surfaces < 15,
        # mais on les ignore pour le calcul du prix/m²
        df["prix_m2_safe"] = None
        mask_ok = (
            df["Surface_m2"].notna() &
            (df["Surface_m2"] >= 15) &
            (df["Surface_m2"] <= 1000) &
            df["Prix"].notna()
        )
        df.loc[mask_ok, "prix_m2_safe"] = (
            df.loc[mask_ok, "Prix"] / df.loc[mask_ok, "Surface_m2"]
        ).round(0)

        # Département en texte, avec zfill pour '06'
        df["Departement"] = df["Departement"].astype(str).str.zfill(2)

        # ✅ jitter déterministe (stable même si cache vidé)
        def stable_jitter(val, key, scale=0.005):
            h = hashlib.md5(str(key).encode("utf-8")).hexdigest()
            r = int(h[:8], 16) / 0xFFFFFFFF  # [0,1)
            return val + (r - 0.5) * 2 * scale

        if "URL" in df.columns:
            keys = df["URL"].astype(str)
        else:
            keys = df.index.astype(str)

        df['lat_viz'] = [stable_jitter(lat, k, 0.004) for lat, k in zip(df['latitude'], keys)]
        df['lon_viz'] = [stable_jitter(lon, k + "_x", 0.004) for lon, k in zip(df['longitude'], keys)]

        return df



    
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    FILE_NAME = os.path.join(SCRIPT_DIR, "..", "data", "annonces_clean.csv")

    try:
        df = load_and_prepare_data(FILE_NAME)
    except FileNotFoundError:
        st.error(f"Fichier '{FILE_NAME}' introuvable.")
        st.stop()

    # --- 2. FILTRES ---
    st.sidebar.header("🔍 Filtres de recherche")

    # Filtre DÉPARTEMENT
    depts_dispos = sorted(df["Departement"].unique())
    options_dept = ["Tous les départements"] + depts_dispos

    dept_choice = st.sidebar.selectbox("📍 Département", options_dept, index=0)

    if dept_choice == "Tous les départements":
        df_dept = df
    else:
        df_dept = df[df["Departement"] == dept_choice]

    # --- Sélecteur VILLE (dépend du département) ---
    villes_dispos = sorted(df_dept["Ville"].dropna().astype(str).unique())
    options_ville = ["Toutes les villes"] + villes_dispos

    ville_choice = st.sidebar.selectbox("🏙️ Ville", options_ville, index=0)

    if ville_choice == "Toutes les villes":
        df_zone = df_dept
    else:
        df_zone = df_dept[df_dept["Ville"].astype(str) == ville_choice]



    # ✅ Garde-fou
    if df_zone.empty:
        st.warning("Aucune annonce pour cette sélection.")
        st.stop()

    # --- PRIX ---
    min_price = int(df_zone["Prix"].min())
    max_price = int(df_zone["Prix"].max())

    if min_price == max_price:
        st.sidebar.info(f"💰 Budget fixe : {min_price:,} €".replace(",", " "))
        prix_range = (min_price, max_price)
    else:
        prix_range = st.sidebar.slider("💰 Budget (€)", min_price, max_price, (min_price, max_price))

    # --- SURFACE ---
    min_surf = float(df_zone["Surface_m2"].min())
    max_surf = float(df_zone["Surface_m2"].max())

    if min_surf == max_surf:
        st.sidebar.info(f"📏 Surface fixe : {min_surf:.0f} m²")
        surf_range = (min_surf, max_surf)
    else:
        surf_range = st.sidebar.slider("📏 Surface (m²)", float(min_surf), float(max_surf), (float(min_surf), float(max_surf)))

    # --- TYPE DE BIEN ---
    if "Type_Bien" in df_zone.columns:
        types_dispos = sorted(df_zone["Type_Bien"].dropna().astype(str).unique())
        options_types = ["Tous les types"] + types_dispos

        type_choice = st.sidebar.selectbox("🏠 Type de bien", options_types, index=0)
    else:
        type_choice = "Tous les types"


    df_filtered = df_zone[
        (df_zone["Prix"] >= prix_range[0]) &
        (df_zone["Prix"] <= prix_range[1]) &
        (df_zone["Surface_m2"] >= surf_range[0]) &
        (df_zone["Surface_m2"] <= surf_range[1])
    ]

    # Filtre Type de bien (si différent de "Tous")
    if type_choice != "Tous les types":
        df_filtered = df_filtered[df_filtered["Type_Bien"].astype(str) == type_choice]



    # --- AFFICHAGE DES STATS ---
    nb_biens = len(df_filtered)

    prix_moyen = int(df_filtered["Prix"].mean()) if not df_filtered.empty else 0
    prix_median = int(df_filtered["Prix"].median()) if not df_filtered.empty else 0

    # Prix au m² sécurisé (>= 15 m² uniquement)
    df_m2 = df_filtered["prix_m2_safe"].dropna()
    prix_m2_moyen = int(df_m2.mean()) if not df_m2.empty else 0
    prix_m2_median = int(df_m2.median()) if not df_m2.empty else 0

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Biens trouvés", nb_biens)
    col2.metric("Prix moyen", f"{prix_moyen:,} €".replace(",", " "))
    col3.metric("Prix médian", f"{prix_median:,} €".replace(",", " "))
    col4.metric("Prix moyen / m²", f"{prix_m2_moyen:,} €/m²".replace(",", " "))
    col5.metric("Prix médian / m²", f"{prix_m2_median:,} €/m²".replace(",", " "))


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
        surf_str = f"{row['Surface_m2']:.0f} m²"

        tooltip_html = f"<b>{prix_str}</b><br>{surf_str}"

        # ✅ MODIF : popup un peu plus robuste + lien si URL dispo (optionnel)
        ville = row['Ville'] if 'Ville' in df_filtered.columns else ""
        popup_html = f"{ville}: {prix_str}"
        if 'URL' in df_filtered.columns and pd.notna(row['URL']):
            popup_html += f'<br><a href="{row["URL"]}" target="_blank">Ouvrir l’annonce</a>'

        folium.CircleMarker(
            location=[row['lat_viz'], row['lon_viz']],
            radius=6,
            color="#3186cc",
            fill=True,
            fill_opacity=0.7,
            tooltip=tooltip_html,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)





    # --- 4. AFFICHAGE OPTIMISÉ ---


    map_key = str((dept_choice, ville_choice, prix_range, surf_range, type_choice))
    st_folium(m, width=None, height=600, returned_objects=[], key=map_key)

with tab_analyses:
    st.subheader("1) Graphique 1 : Histogramme de la distribution des prix")

    st.markdown("**Comment se répartissent les prix des biens sélectionnés ?**")

    if df_filtered.empty:
        st.warning("Aucune donnée pour cette sélection.")
        st.stop()

    # --- Histogramme des prix ---
    fig_prix = px.histogram(
        df_filtered,
        x="Prix",
        nbins=30,
        title="Distribution des prix des biens (€)",
        labels={"Prix": "Prix (€)"}
    )
    fig_prix.update_layout(
        yaxis_title="Nombre de biens",
        bargap=0.05
    )

    st.plotly_chart(fig_prix, use_container_width=True)

    is_global_view = (
        dept_choice == "Tous les départements" and
        ville_choice == "Toutes les villes" and
        type_choice == "Tous les types"
    )

    # Données communes
    prix_min = int(df_filtered["Prix"].min())
    prix_max = int(df_filtered["Prix"].max())
    prix_median = int(df_filtered["Prix"].median())
    nb_biens = len(df_filtered)

    if is_global_view:
        # --- Conclusion GÉNÉRALE ---
        st.markdown(
            """
            La distribution des prix est fortement asymétrique.  
            La majorité des biens se situe dans les gammes de prix les plus basses, tandis qu’un nombre
            restreint de biens haut de gamme étend la distribution vers des prix très élevés.
            Cela explique l’écart observé entre le prix moyen et le prix médian.
            """
        )
    else:
        # --- Conclusion DYNAMIQUE (quand filtres actifs) ---
        st.markdown(
            f"""
            Pour la sélection actuelle (**{nb_biens} biens**), les prix s’échelonnent de  
            **{prix_min:,} €** à **{prix_max:,} €**, avec un **prix médian autour de {prix_median:,} €**.  
            La majorité des biens se concentre autour de cette valeur, tandis que quelques biens
            plus chers étendent la distribution vers le haut.
            """.replace(",", " ")
        )


 


    st.subheader("2) Graphique 2 : Prix en fonction de la surface")

    # Question (toujours affichée)
    st.markdown("**Comment évolue le prix d'un bien en fonction de sa surface ?**")

    df_scatter = df_filtered.dropna(subset=["Surface_m2", "Prix"])

    if df_scatter.empty:
        st.warning("Pas assez de données pour analyser la relation prix / surface.")
    else:
        # Créer une colonne simplifiée pour le type (Maison vs Appartement)
        df_scatter = df_scatter.copy()
        df_scatter['Type_Simple'] = df_scatter['Type_Bien'].apply(
            lambda x: 'Maison' if 'Maison' in str(x) else 'Appartement'
        )
        
        fig_surface_prix = px.scatter(
            df_scatter,
            x="Surface_m2",
            y="Prix",
            color="Type_Simple",  # Couleur par type
            color_discrete_map={
                "Maison": "#e36811",      # Vert pour les maisons
                "Appartement": "#3498db"   # Bleu pour les appartements
            },
            title="Relation entre la surface (m²) et le prix (€)",
            labels={
                "Surface_m2": "Surface (m²)", 
                "Prix": "Prix (€)",
                "Type_Simple": "Type de bien"
            },
            opacity=0.6
        )
        
        # Améliorer la légende
        fig_surface_prix.update_layout(
            legend=dict(
                title="Type de bien",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)"
            )
        )
        fig_surface_prix.update_yaxes(
            range=[0, 2_000_000]  # à adapter à ton dataset
        )

        st.plotly_chart(fig_surface_prix, use_container_width=True)

        # Conclusion générale uniquement sans filtres
        if is_global_view:
            st.markdown(
                """
                Le prix des biens augmente globalement avec la surface, ce qui confirme une relation positive entre ces deux variables.
        
                **Observations par type de bien :**
                - 🔵 **Appartements** : Concentrés sur les petites surfaces (< 150 m²), mais avec des prix pouvant atteindre 3-4 M€. 
                Cela reflète l'effet localisation (Paris, Côte d'Azur) où le prix au m² est très élevé.
                - 🟢 **Maisons** : Surfaces plus variées (50 à 850 m²), avec une progression de prix plus linéaire. 
                Les maisons les plus chères combinent grande surface ET localisation premium.
                
                **Point notable** : Pour une même surface (~100 m²), un appartement peut coûter plus cher qu'une maison, 
                ce qui s'explique par la localisation urbaine des appartements vs. périurbaine/rurale des maisons.
                """
            )

    st.subheader("3) Graphique 3 : Prix médian au m² par territoire")
    st.markdown("**Question :** Quels territoires sont les plus chers au m² (prix médian / m²) ?")

    # Base fiable pour le prix/m² (surface >= 15 m² déjà filtrée en amont)
    df_m2 = df_filtered.dropna(subset=["prix_m2_safe"])

    if df_m2.empty:
        st.warning("Pas assez de données fiables pour calculer le prix au m² (surface ≥ 15 m²).")

    else:
        # --- CAS 1 : Tous les départements -> Top 15 départements ---
        if dept_choice == "Tous les départements":
            agg = (
                df_m2.groupby("Departement")["prix_m2_safe"]
                .median()
                .sort_values(ascending=True)
                .tail(15)
                .reset_index()
                .rename(columns={"prix_m2_safe": "prix_m2_median"})
            )

            agg["Territoire"] = agg["Departement"].apply(
                lambda d: f"Département {str(d).zfill(2)}"
            )

            fig = px.bar(
                agg,
                x="prix_m2_median",
                y="Territoire",
                orientation="h",
                title="Top 15 départements — prix médian / m² (€/m²)",
                labels={
                    "prix_m2_median": "Prix médian / m² (€/m²)",
                    "Territoire": "Territoire"
                },
                text="prix_m2_median"
            )
            fig.update_traces(
                texttemplate="%{text:.0f} €/m²",
                textposition="outside"
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

        # --- CAS 2 : Département sélectionné + toutes les villes ---
        elif ville_choice == "Toutes les villes":
            agg = (
                df_m2.groupby("Ville")["prix_m2_safe"]
                .median()
                .sort_values(ascending=True)
                .tail(15)
                .reset_index()
                .rename(columns={"prix_m2_safe": "prix_m2_median"})
            )

            fig = px.bar(
                agg,
                x="prix_m2_median",
                y="Ville",
                orientation="h",
                title=f"Top 15 villes — Département {dept_choice} — prix médian / m² (€/m²)",
                labels={
                    "prix_m2_median": "Prix médian / m² (€/m²)",
                    "Ville": "Ville"
                },
                text="prix_m2_median"
            )
            fig.update_traces(
                texttemplate="%{text:.0f} €/m²",
                textposition="outside"
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

        # --- CAS 3 : Ville sélectionnée -> rang dans le département ---
        else:
            # Classement département COMPLET (pas filtré par ville)
            df_dept_m2 = df_dept.dropna(subset=["prix_m2_safe"])

            classement = (
                df_dept_m2.groupby("Ville")["prix_m2_safe"]
                .median()
                .sort_values(ascending=False)
            )

            if ville_choice not in classement.index:
                st.warning(
                    "Impossible de déterminer le classement de cette ville "
                    "(données insuffisantes)."
                )
            else:
                prix_ville = int(classement.loc[ville_choice])
                rang = int(classement.index.get_loc(ville_choice)) + 1
                total = len(classement)

                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Prix médian / m²",
                    f"{prix_ville:,} €/m²".replace(",", " ")
                )
                c2.metric(
                    "Rang dans le département",
                    f"{rang} / {total}"
                )
                c3.metric(
                    "Département",
                    f"{dept_choice}"
                )

                # Bonus informatif
                nb_biens = df_dept_m2[df_dept_m2["Ville"] == ville_choice].shape[0]
                st.caption(
                    f"Médiane calculée sur {nb_biens} biens "
                    f"(surface ≥ 15 m²)."
                )


    st.subheader("4) Graphique 4 : Distribution des prix au m² par territoire")

    st.markdown("**Question : Comment se distribue le prix au m² selon les territoires ? Y a-t-il des disparités importantes ?**")

    # Base fiable pour le prix/m² (surface >= 15 m²)
    df_box = df_filtered.dropna(subset=["prix_m2_safe"]).copy()

    if df_box.empty:
        st.warning("Pas assez de données fiables pour afficher la distribution (surface ≥ 15 m²).")

    else:
        # --- CAS 1 : Tous les départements → Boxplot par département ---
        if dept_choice == "Tous les départements":
            # Convertir en string pour que ce soit traité comme catégorie
            df_box['Dept_str'] = "Dép. " + df_box['Departement'].astype(str).str.zfill(2)
            
            # Trier par numéro de département
            ordre_dept = sorted(df_box['Dept_str'].unique())
            
            fig_box = px.box(
                df_box,
                x="Dept_str",
                y="prix_m2_safe",
                color="Dept_str",
                category_orders={"Dept_str": ordre_dept},
                title="Distribution des prix au m² par département",
                labels={
                    "prix_m2_safe": "Prix au m² (€/m²)",
                    "Dept_str": "Département"
                }
            )
            
            fig_box.update_layout(
                showlegend=False,
                xaxis_tickangle=-45,
                height=500,  # Plus grand
                bargap=0.3   # Espacement entre les boxplots
            )
            
            # Largeur des boxplots
            fig_box.update_traces(width=0.6)
            
            st.plotly_chart(fig_box, use_container_width=True)
            
            # Conclusion générale
            if is_global_view:
                st.markdown(
                    """
                    **Analyse de la distribution :**
                    
                    Les boxplots révèlent d'importantes disparités entre départements :
                    - **Paris (75)** se distingue nettement avec des prix au m² bien supérieurs aux autres territoires 
                    et une forte dispersion (du studio au bien de luxe).
                    - **Les départements côtiers** (06, 83) affichent également des prix élevés avec une variabilité importante.
                    - **Les départements moins urbains** présentent des distributions plus resserrées autour de valeurs médianes plus basses.
                    
                    Les points au-delà des moustaches représentent les biens atypiques (très haut de gamme ou situations exceptionnelles).
                    """
                )
        
        # --- CAS 2 : Département sélectionné → Boxplot par ville ---
        elif ville_choice == "Toutes les villes":
            # Prendre les 15 villes avec le plus d'annonces pour lisibilité
            top_villes = df_box['Ville'].value_counts().head(15).index.tolist()
            df_box_villes = df_box[df_box['Ville'].isin(top_villes)]
            
            if df_box_villes.empty:
                st.warning("Pas assez de données pour afficher le boxplot par ville.")
            else:
                fig_box = px.box(
                    df_box_villes,
                    x="Ville",
                    y="prix_m2_safe",
                    color="Ville",
                    title=f"Distribution des prix au m² — Top 15 villes du département {dept_choice}",
                    labels={
                        "prix_m2_safe": "Prix au m² (€/m²)",
                        "Ville": "Ville"
                    }
                )
                fig_box.update_layout(showlegend=False)
                fig_box.update_xaxes(tickangle=45)
                
                st.plotly_chart(fig_box, use_container_width=True)
                
                st.markdown(
                    f"""
                    **Analyse pour le département {dept_choice} :**
                    
                    Ce graphique compare la distribution des prix au m² entre les principales villes du département.
                    La hauteur des boîtes indique la variabilité des prix : une boîte haute signifie des prix très hétérogènes,
                    tandis qu'une boîte compacte indique un marché plus homogène.
                    """
                )
        
        # --- CAS 3 : Ville sélectionnée → Boxplot par type de bien ---
        else:
            # Créer une colonne Type simplifié
            df_box = df_box.copy()
            df_box['Type_Simple'] = df_box['Type_Bien'].apply(
                lambda x: 'Maison' if 'Maison' in str(x) else 'Appartement'
            )
            
            fig_box = px.box(
                df_box,
                x="Type_Simple",
                y="prix_m2_safe",
                color="Type_Simple",
                color_discrete_map={
                    "Maison": "#2ecc71",
                    "Appartement": "#3498db"
                },
                title=f"Distribution des prix au m² à {ville_choice} — par type de bien",
                labels={
                    "prix_m2_safe": "Prix au m² (€/m²)",
                    "Type_Simple": "Type de bien"
                }
            )
            fig_box.update_layout(showlegend=False)
            
            st.plotly_chart(fig_box, use_container_width=True)
            
            st.markdown(
                f"""
                **Analyse pour {ville_choice} :**
                
                Ce boxplot compare la distribution des prix au m² entre maisons et appartements dans cette ville.
                La ligne centrale représente la médiane, la boîte contient 50% des biens (du 1er au 3ème quartile).
                """
            )










