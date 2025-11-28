import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from urllib.parse import urljoin


# Vos fonctions d'extraction d'annonces
def extraire_titre(soup):
    try:
        titre_element = soup.find('h1')
        return titre_element.get_text().strip() if titre_element else ''
    except:
        return ''


def extraire_prix(soup):
    try:
        prix_div = soup.find('p', string='Prix').find_parent('div')
        if prix_div:
            prix_element = prix_div.find_all('p')[1]
            if prix_element:
                prix_text = prix_element.get_text().strip()
                chiffres = re.findall(r'\d+', prix_text)
                return int(''.join(chiffres)) if chiffres else 0
        return 0
    except:
        return 0


def extraire_surface(soup):
    try:
        surface_div = soup.find('p', string='Surface').find_parent('div')
        if surface_div:
            surface_element = surface_div.find_all('p')[1]
            if surface_element:
                surface_text = surface_element.get_text().strip()
                chiffres = re.findall(r'\d+', surface_text)
                return int(chiffres[0]) if chiffres else 0
        return 0
    except:
        return 0


def extraire_pieces(soup):
    try:
        pieces_element = soup.find('p', string='Pièces')
        if pieces_element:
            parent_div = pieces_element.find_parent('div')
            if parent_div:
                valeur_element = parent_div.find_all('p')[1]
                if valeur_element:
                    return int(re.search(r'\d+', valeur_element.get_text()).group())
        return 0
    except:
        return 0


def extraire_adresse_complete(soup):
    """
    Extrait l'adresse complète avec le bon sélecteur
    """
    try:
        # Sélecteur exact basé sur votre capture
        adresse_element = soup.find('p', class_='text-sm text-grey-400 md:text-base')

        if adresse_element:
            adresse_text = adresse_element.get_text().strip()
            return adresse_text

        return ''

    except Exception as e:
        print(f"Erreur extraction adresse: {e}")
        return ''


def extraire_type_bien(soup):
    try:
        type_div = soup.find('p', string='Type de bien').find_parent('div')
        if type_div:
            type_element = type_div.find_all('p')[1]
            if type_element:
                type_text = type_element.get_text().strip().lower()
                if 'appartement' in type_text:
                    return 'appartement'
                elif 'maison' in type_text:
                    return 'maison'
                elif 'studio' in type_text:
                    return 'studio'
                else:
                    return type_text
        return ''
    except:
        return ''


def scrape_locamoi(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        annonce = {}

        # Extraction des champs essentiels seulement
        annonce['titre'] = extraire_titre(soup)
        annonce['prix'] = extraire_prix(soup)
        annonce['surface'] = extraire_surface(soup)
        annonce['pieces'] = extraire_pieces(soup)
        annonce['adresse'] = extraire_adresse_complete(soup)
        annonce['type_bien'] = extraire_type_bien(soup)

        return annonce

    except Exception as e:
        print(f"❌ Erreur sur {url}: {e}")
        return None


def extraire_urls_annonces_page(url_page):
    """
    Extrait toutes les URLs d'annonces d'une page de résultats
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url_page, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        urls_annonces = []

        liens = soup.find_all('a', href=re.compile(r'/listings/'))

        for lien in liens:
            href = lien.get('href')
            if href and '/listings/' in href:
                url_complete = urljoin('https://www.locamoi.fr', href)
                if url_complete not in urls_annonces:
                    urls_annonces.append(url_complete)

        return urls_annonces[:20]

    except Exception as e:
        print(f"❌ Erreur extraction URLs depuis {url_page}: {e}")
        return []


def generer_urls_recherche(villes, pages=4):
    """
    Génère les URLs de recherche pour chaque ville et chaque page
    """
    urls_recherche = []

    for ville in villes:
        for page in range(1, pages + 1):
            url = f"https://locamoi.fr/location/{ville.lower()}?page={page}"
            urls_recherche.append((ville, page, url))

    return urls_recherche


def collecter_annonces_multivilles(villes, pages_par_ville=4):
    """
    Collecte les annonces pour plusieurs villes sur plusieurs pages
    """
    toutes_annonces = []
    urls_recherche = generer_urls_recherche(villes, pages_par_ville)

    print(f"🎯 Début de la collecte sur {len(villes)} villes, {pages_par_ville} pages par ville")

    for ville, page, url_recherche in urls_recherche:
        print(f"\n🔍 Ville: {ville}, Page: {page}")

        urls_annonces = extraire_urls_annonces_page(url_recherche)
        print(f"   ✅ {len(urls_annonces)} annonces trouvées")

        for i, url_annonce in enumerate(urls_annonces, 1):
            print(f"      📝 Annonce {i}/{len(urls_annonces)}...")

            annonce = scrape_locamoi(url_annonce)
            if annonce:
                toutes_annonces.append(annonce)
                print(f"         📍 {annonce['adresse']} - {annonce['prix']}€ - {annonce['surface']}m²")

            time.sleep(4)

        time.sleep(6)

    return pd.DataFrame(toutes_annonces)


# CONFIGURATION
VILLES = [
    'Paris', 'Lyon', 'Marseille', 'Lille', 'Angers',
    'Montpellier', 'Toulouse', 'Nice', 'Strasbourg', 'Bordeaux'
]

# LANCEMENT
if __name__ == "__main__":
    print("🚀 LANCEMENT DU SCRAPER LOCAMOI - VERSION FINALE")
    print("=" * 50)

    # TEST sur 1 ville, 1 page d'abord
    VILLES_TEST = ['Paris']
    PAGES_TEST = 1

    debut = time.time()
    df_annonces = collecter_annonces_multivilles(VILLES_TEST, PAGES_TEST)
    fin = time.time()
    duree = fin - debut

    # Sauvegarde
    if not df_annonces.empty:
        nom_fichier = f"locamoi_annonces.csv"
        df_annonces.to_csv(nom_fichier, index=False, encoding='utf-8')

        print(f"\n🎉 COLLECTE TERMINÉE !")
        print(f"📈 {len(df_annonces)} annonces collectées")
        print(f"⏱️  Durée: {duree:.2f} secondes")
        print(f"💾 Fichier sauvegardé: {nom_fichier}")

        # Aperçu des données
        print(f"\n📊 COLONNES FINALES:")
        print(df_annonces.columns.tolist())
        print(f"\n👀 APERÇU DES DONNÉES:")
        print(df_annonces.head())

    else:
        print("❌ Aucune annonce collectée")
