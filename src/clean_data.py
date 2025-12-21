"""
clean_data.py - Script de nettoyage des données immobilières

Ce script transforme les données brutes du scraping en un fichier propre
prêt pour l'application Streamlit.

Entrée  : data/annonces_raw.csv
Sortie  : data/annonces_clean.csv

Transformations effectuées :
1. Extraction des surfaces manquantes depuis les descriptions
2. Suppression des lignes sans surface
3. Création de la colonne Ville
4. Création de la colonne prix_m2
5. Géocodage des villes (latitude, longitude)

"""

import pandas as pd
import re
import time
from pathlib import Path

# Import conditionnel pour le géocodage
try:
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    print("⚠️  geopy non installé. Le géocodage sera ignoré.")
    print("   Pour l'installer : pip install geopy")


# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_FILE = Path("data/annonces_raw.csv")
OUTPUT_FILE = Path("data/annonces_clean.csv")

# Patterns regex pour extraire la surface depuis la description
SURFACE_PATTERNS = [
    r"(\d+(?:[.,]\d+)?)\s*m²",   # m² standard (ex: "72.12 m²")
    r"(\d+(?:[.,]\d+)?)\s*m2",    # m2 sans accent (ex: "67 m2")
]

# Configuration Nominatim
NOMINATIM_USER_AGENT = "projet_immobilier_sorbonne"
NOMINATIM_DELAY = 1.0  # Délai entre requêtes (respect API)


# =============================================================================
# FONCTIONS DE NETTOYAGE
# =============================================================================

def extraire_surface(description: str, type_bien: str = None) -> float | None:
    """
    Extraction INTELLIGENTE de la surface depuis une description.
    
    Évite les pièges courants : balcons, caves, terrasses, greniers
    qui sont souvent mentionnés avec leur surface dans les descriptions.
    
    Priorité d'extraction :
    1. Surface Carrez (la plus fiable juridiquement)
    2. Surface "habitable" 
    3. Surface après "de" ou "d'environ" (formulation standard)
    4. Plus grande surface au-dessus d'un seuil minimum
    
    Le seuil minimum est adapté selon le type de bien (studios vs T2+).
    
    Args:
        description: Texte de la description de l'annonce
        type_bien: Type du bien (ex: "Appartement T2") pour adapter le seuil
        
    Returns:
        Surface en m² (float) ou None si non trouvée
    """
    desc = str(description)
    pattern = r"(\d+(?:[.,]\d+)?)\s*m[²2]"
    
    # Définir le seuil minimum selon le type de bien
    # Les studios (T0, T1) peuvent être petits, les T2+ rarement < 25m²
    if type_bien and ('T0' in str(type_bien) or 'T1' in str(type_bien)):
        seuil_min = 12
    else:
        seuil_min = 25
    
    # --- Priorité 1 : Surface Carrez (mention légale, très fiable) ---
    carrez = re.search(r"(\d+(?:[.,]\d+)?)\s*m[²2]\s*(?:carrez|loi carrez)", desc, re.IGNORECASE)
    if carrez:
        return float(carrez.group(1).replace(',', '.'))
    
    # --- Priorité 2 : Surface habitable ---
    habitable = re.search(r"(\d+(?:[.,]\d+)?)\s*m[²2]\s*habitables?", desc, re.IGNORECASE)
    if habitable:
        return float(habitable.group(1).replace(',', '.'))
    
    # --- Priorité 3 : Formulations courantes "de X m²" ---
    # Capture : "appartement de 75 m²", "d'environ 80 m²", "d'une surface de 65 m²"
    formulation = re.search(
        r"(?:de|d'environ|d'une surface de)\s*(\d+(?:[.,]\d+)?)\s*m[²2]", 
        desc, re.IGNORECASE
    )
    if formulation:
        val = float(formulation.group(1).replace(',', '.'))
        if val >= seuil_min:
            return val
    
    # --- Priorité 4 : Plus grande surface au-dessus du seuil ---
    # Évite de prendre la surface d'un balcon (6m²) ou d'une cave (4m²)
    matches = re.findall(pattern, desc, re.IGNORECASE)
    if matches:
        values = [float(m.replace(',', '.')) for m in matches]
        valid = [v for v in values if v >= seuil_min]
        if valid:
            return max(valid)
        # Si tout est sous le seuil, prendre le max (cas très rare)
        return max(values)
    
    # --- Priorité 5 : Pattern "environ X" sans m² ---
    environ = re.search(r"environ\s*(\d+)", desc, re.IGNORECASE)
    if environ:
        val = float(environ.group(1))
        if val >= seuil_min:
            return val
    
    return None


def extraire_ville(localisation: str) -> str:
    """
    Extrait le nom de la ville depuis la colonne Localisation.
    
    Format attendu : "- Ville - Département (XX)"
    Exemple : "- Paris 8 - Paris (75)" → "Paris 8"
    
    Args:
        localisation: Chaîne de localisation brute
        
    Returns:
        Nom de la ville nettoyé
    """
    # Retirer le tiret initial et les espaces
    texte = str(localisation).lstrip('- ').strip()
    
    # Prendre la partie avant le second tiret
    if ' - ' in texte:
        return texte.split(' - ')[0].strip()
    return texte


def extraire_nom_departement(localisation: str) -> str:
    """
    Extrait le nom du département depuis la colonne Localisation.
    
    Format attendu : "- Ville - Département (XX)"
    Exemple : "- Tarascon - Bouches-du-Rhône (13)" → "Bouches-du-Rhône"
    
    Args:
        localisation: Chaîne de localisation brute
        
    Returns:
        Nom du département ou chaîne vide si non trouvé
    """
    texte = str(localisation).lstrip('- ').strip()
    
    # Chercher la partie après le second tiret
    if ' - ' in texte:
        partie_dept = texte.split(' - ')[1].strip()
        # Retirer le code département entre parenthèses : "Bouches-du-Rhône (13)" → "Bouches-du-Rhône"
        if '(' in partie_dept:
            return partie_dept.split('(')[0].strip()
        return partie_dept
    return ""


def nettoyer_donnees(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique toutes les transformations de nettoyage.
    
    Args:
        df: DataFrame brut
        
    Returns:
        DataFrame nettoyé
    """
    print("\n📊 Nettoyage des données...")
    initial_count = len(df)
    
    # --- 1. Extraction des surfaces manquantes ---
    print("\n1️⃣  Extraction des surfaces depuis les descriptions...")
    mask_missing = df['Surface_m2'].isna()
    missing_count = mask_missing.sum()
    print(f"   Surfaces manquantes : {missing_count}")
    
    # Appliquer l'extraction intelligente (avec type de bien pour adapter le seuil)
    df.loc[mask_missing, 'Surface_m2'] = df.loc[mask_missing].apply(
        lambda row: extraire_surface(row['Description'], row['Type_Bien']), 
        axis=1
    )
    
    recovered = missing_count - df['Surface_m2'].isna().sum()
    print(f"   Récupérées par regex intelligent : {recovered}")
    
    # --- 2. Suppression des lignes sans surface ---
    print("\n2️⃣  Suppression des lignes sans surface...")
    still_missing = df['Surface_m2'].isna().sum()
    df = df.dropna(subset=['Surface_m2']).copy()
    print(f"   Lignes supprimées : {still_missing}")
    print(f"   Lignes restantes : {len(df)}")
    
    # --- 3. Création de la colonne Ville ---
    print("\n3️⃣  Extraction des noms de ville...")
    df['Ville'] = df['Localisation'].apply(extraire_ville)
    print(f"   Villes uniques : {df['Ville'].nunique()}")
    
    # --- 3bis. Extraction du nom de département (pour géocodage précis) ---
    df['Nom_Departement'] = df['Localisation'].apply(extraire_nom_departement)
    
    # --- 4. Calcul du prix au m² ---
    print("\n4️⃣  Calcul du prix au m²...")
    df['prix_m2'] = (df['Prix'] / df['Surface_m2']).round(2)
    print(f"   Prix/m² médian : {df['prix_m2'].median():,.0f} €/m²")
    
    # --- Résumé ---
    print(f"\n✅ Nettoyage terminé : {initial_count} → {len(df)} lignes")
    
    return df


# =============================================================================
# FONCTIONS DE GÉOCODAGE
# =============================================================================

def construire_query_geocodage(ville: str, nom_departement: str = "") -> str:
    """
    Construit la requête de géocodage adaptée.
    
    Gère les cas spéciaux des arrondissements Paris/Lyon/Marseille
    en les convertissant en codes postaux pour une meilleure précision.
    
    Pour les autres villes, ajoute le nom du département pour éviter
    les ambiguïtés (ex: Tarascon existe dans plusieurs départements).
    
    Args:
        ville: Nom de la ville (ex: "Paris 8", "Grenoble", "Tarascon")
        nom_departement: Nom du département (ex: "Bouches-du-Rhône")
        
    Returns:
        Query pour Nominatim (ex: "75008, France", "Tarascon, Bouches-du-Rhône, France")
    """
    # Pattern pour détecter Paris/Lyon/Marseille + arrondissement
    match = re.search(r"(paris|lyon|marseille)\s*0*(\d+)", str(ville).lower().strip())
    
    if match:
        nom_ville = match.group(1)
        arrondissement = int(match.group(2))
        
        # Codes postaux de base
        base_cp = {
            'paris': 75000,
            'lyon': 69000,
            'marseille': 13000
        }
        
        cp = base_cp.get(nom_ville, 0)
        if cp > 0:
            return f"{cp + arrondissement}, France"
    
    # Cas standard : ajouter le département pour plus de précision
    if nom_departement:
        return f"{ville}, {nom_departement}, France"
    else:
        return f"{ville}, France"


def geocoder_villes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les coordonnées GPS (latitude, longitude) pour chaque ville.
    
    Utilise un cache pour ne géocoder chaque combinaison ville+département 
    qu'une seule fois. Le nom du département est ajouté à la requête pour
    éviter les ambiguïtés (ex: Tarascon existe en Bouches-du-Rhône et en Ariège).
    
    Args:
        df: DataFrame avec colonnes 'Ville' et 'Nom_Departement'
        
    Returns:
        DataFrame avec colonnes 'latitude' et 'longitude'
    """
    if not GEOPY_AVAILABLE:
        print("\n⚠️  Géocodage ignoré (geopy non disponible)")
        df['latitude'] = None
        df['longitude'] = None
        return df
    
    print("\n🌍 Géocodage des villes...")
    
    # Initialiser le géocodeur
    geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT)
    
    # Identifier les combinaisons (ville, département) uniques
    # Cela évite de géocoder "Tarascon, Bouches-du-Rhône" et "Tarascon, Ariège" de la même façon
    couples_uniques = df[['Ville', 'Nom_Departement']].drop_duplicates()
    print(f"   Combinaisons ville+département uniques : {len(couples_uniques)}")
    print(f"   Temps estimé : ~{len(couples_uniques)} secondes")
    
    # Cache des coordonnées : clé = (ville, département)
    cache = {}
    
    for i, (_, row) in enumerate(couples_uniques.iterrows()):
        ville = row['Ville']
        nom_dept = row['Nom_Departement']
        cache_key = (ville, nom_dept)
        
        try:
            query = construire_query_geocodage(ville, nom_dept)
            location = geolocator.geocode(query, timeout=10)
            
            if location:
                cache[cache_key] = (location.latitude, location.longitude)
            else:
                print(f"   ⚠️  Non trouvé : {ville} ({nom_dept})")
                cache[cache_key] = (None, None)
                
        except Exception as e:
            print(f"   ❌ Erreur sur {ville} ({nom_dept}) : {e}")
            cache[cache_key] = (None, None)
        
        # Pause pour respecter l'API
        time.sleep(NOMINATIM_DELAY)
        
        # Indicateur de progression
        if (i + 1) % 20 == 0 or (i + 1) == len(couples_uniques):
            print(f"   ... {i + 1}/{len(couples_uniques)} villes traitées")
    
    # Appliquer les coordonnées au DataFrame
    def get_coords(row):
        key = (row['Ville'], row['Nom_Departement'])
        return cache.get(key, (None, None))
    
    coords = df.apply(get_coords, axis=1)
    df['latitude'] = coords.apply(lambda x: x[0])
    df['longitude'] = coords.apply(lambda x: x[1])
    
    # Stats
    geocoded = df['latitude'].notna().sum()
    print(f"\n   ✅ Géocodées : {geocoded}/{len(df)} annonces")
    
    return df


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """Point d'entrée principal du script."""
    
    print("=" * 60)
    print("🏠 NETTOYAGE DES DONNÉES IMMOBILIÈRES")
    print("=" * 60)
    
    # --- Vérification des fichiers ---
    if not INPUT_FILE.exists():
        print(f"\n❌ Erreur : Fichier non trouvé : {INPUT_FILE}")
        print("   Assurez-vous d'avoir exécuté le scraper d'abord.")
        return
    
    # --- Chargement ---
    print(f"\n📂 Chargement de {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    print(f"   {len(df)} annonces chargées")
    
    # --- Nettoyage ---
    df = nettoyer_donnees(df)
    
    # --- Géocodage ---
    df = geocoder_villes(df)
    
    # --- Sauvegarde ---
    print(f"\n💾 Sauvegarde vers {OUTPUT_FILE}...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    # --- Résumé final ---
    print("\n" + "=" * 60)
    print("✅ TRAITEMENT TERMINÉ")
    print("=" * 60)
    print(f"\nFichier créé : {OUTPUT_FILE}")
    print(f"Lignes : {len(df)}")
    print(f"Colonnes : {list(df.columns)}")
    print(f"\nAperçu :")
    print(df[['Ville', 'Prix', 'Surface_m2', 'prix_m2', 'latitude', 'longitude']].head())


if __name__ == "__main__":
    main()
