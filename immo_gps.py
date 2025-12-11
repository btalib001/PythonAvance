import pandas as pd
from geopy.geocoders import Nominatim
import time


def enrichir_csv_avec_gps(input_file, output_file):
    """
    Lit un CSV contenant une colonne 'Ville', ajoute Latitude/Longitude
    et sauvegarde le résultat.
    """
    print(f"Chargement du fichier : {input_file}")
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print("Erreur : Le fichier n'a pas été trouvé.")
        return


    # Initialisation du géocodeur
    # IMPORTANT : Change le user_agent pour mettre le nom de ton projet
    geolocator = Nominatim(user_agent="Python_avance")

    # --- OPTIMISATION ---
    # On ne géocode que les villes uniques pour gagner du temps et épargner l'API
    villes_uniques = df['Ville'].unique()
    cache_coordonnees = {}

    print(f"{len(villes_uniques)} villes uniques trouvées. Début du géocodage...")
    print("Cela peut prendre du temps (1 seconde par ville pour respecter l'API)...")

    for i, ville in enumerate(villes_uniques):
        try:
            # On ajoute ", France" pour la précision
            query = f"{ville}, France"
            location = geolocator.geocode(query, timeout=10)

            if location:
                cache_coordonnees[ville] = (location.latitude, location.longitude)
            else:
                print(f" -> Introuvable : {ville}")
                cache_coordonnees[ville] = None
        except Exception as e:
            print(f" -> Erreur sur {ville} : {e}")
            cache_coordonnees[ville] = None

        # Pause obligatoire pour ne pas être banni par Nominatim (OpenStreetMap)
        time.sleep(1)

        # Petit indicateur de progression
        if (i + 1) % 10 == 0:
            print(f"   ... {i + 1}/{len(villes_uniques)} villes traitées")

    # --- FUSION DES DONNÉES ---
    print("Application des coordonnées au fichier principal...")

    # On crée une colonne temporaire avec le tuple (lat, lon)
    df['temp_coords'] = df['Ville'].map(cache_coordonnees)

    # On supprime les lignes où on n'a pas trouvé de coordonnées
    #lignes_avant = len(df)
    #df = df.dropna(subset=['temp_coords'])
    #lignes_apres = len(df)
    #print(f"Nettoyage : {lignes_avant - lignes_apres} annonces supprimées (ville introuvable).")

    # On sépare en deux colonnes distinctes (plus facile pour Folium ensuite)
    # L'index 0 est la latitude, l'index 1 la longitude
    df['latitude'] = df['temp_coords'].apply(lambda x: x[0])
    df['longitude'] = df['temp_coords'].apply(lambda x: x[1])

    # On supprime la colonne temporaire
    df = df.drop(columns=['temp_coords'])

    # Sauvegarde
    df.to_csv(output_file, index=False)
    print(f"Succès ! Fichier sauvegardé sous : {output_file}")


# --- UTILISATION ---
# Remplace par le nom de tes fichiers
enrichir_csv_avec_gps("immo_final.csv", "immo_gps.csv")