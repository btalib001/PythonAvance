import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- 1. Configuration du Projet ---
# Liste des départements à scraper
departements = ['75', '13', '01', '69', '31', '06', '44', '34', '33', '59', '83', '42', '76', '21', '38']
pages_to_scrape = 5
base_url = "https://www.immobilier.notaires.fr/fr/annonces-immobilieres-liste"

# Liste pour stocker tous les résultats
all_data = []

# --- 2. Configuration de Selenium (Mode Headless) ---
chrome_options = Options()
# Mode Headless (sans interface graphique) pour la rapidité et la stabilité
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# User-Agent pour éviter d'être bloqué
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

# Initialisation du WebDriver
try:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
except Exception as e:
    print(f"Erreur lors de l'initialisation du WebDriver : {e}")
    print("Veuillez vous assurer que Chrome est installé et que vous avez la dernière version de 'webdriver-manager'.")
    exit()

print("--- Démarrage du Scraping multi-niveau (60 pages) ---")

try:
    for dept in departements:
        print(f"\n=== Traitement du Département : {dept} ===")

        for page in range(1, pages_to_scrape + 1):
            # --- Niveau 1 : Charger la page de LISTE ---
            list_url = f"{base_url}?typeBien=APP,MAI&typeTransaction=VENTE,VNI,VAE&departement={dept}&page={page}"
            driver.get(list_url)
            # Attente plus longue pour le chargement initial de la liste
            time.sleep(random.uniform(3, 5))

            soup_list = BeautifulSoup(driver.page_source, 'html.parser')

            # Récupérer tous les liens d'annonces (Sélecteur robuste : href contenant "/annonce-immo/")
            liens_annonces = []
            candidates = soup_list.find_all('a', href=True)
            for cand in candidates:
                if "/annonce-immo/" in cand['href']:
                    full_link = cand['href']
                    if not full_link.startswith('http'):
                        full_link = "https://www.immobilier.notaires.fr" + full_link
                    if full_link not in liens_annonces:
                        liens_annonces.append(full_link)

            print(f"   -> Page {page}: {len(liens_annonces)} annonces détectées.")

            # --- Niveau 2 : Boucler sur chaque lien pour aller chercher le DETAIL ---
            for link in liens_annonces:
                try:
                    driver.get(link)
                    # Pause pour charger la page de détail dynamique
                    time.sleep(random.uniform(2, 4))

                    soup_detail = BeautifulSoup(driver.page_source, 'html.parser')

                    # --- EXTRACTIONS SIMPLES ---
                    titre_tag = soup_detail.find('h1')
                    titre = titre_tag.get_text(strip=True) if titre_tag else "N/A"

                    type_tag = soup_detail.find('span', class_='type_bien')
                    type_de_bien = type_tag.get_text(strip=True) if type_tag else "N/A"

                    loc_tag = soup_detail.find('span', class_='localisation')
                    location = loc_tag.get_text(strip=True) if loc_tag else "N/A"

                    # --- EXTRACTION DESCRIPTION ---
                    desc_tag = soup_detail.find('inotr-description')
                    description = desc_tag.find('p').get_text(separator="\n", strip=True) if desc_tag and desc_tag.find(
                        'p') else "Pas de description"

                    # --- NOUVEAU: Extraction Surface et Pièces (par Label) ---
                    surface = "N/A"
                    nb_pieces = "N/A"

                    # On cherche tous les labels de critères (points d'entrée stables)
                    labels = soup_detail.find_all('div', class_='label_critere')

                    for label_tag in labels:
                        label_text = label_tag.get_text(strip=True).lower()
                        parent_tag = label_tag.find_parent('div', class_='critere_icone')

                        if parent_tag:
                            valeur_tag = parent_tag.find('div', class_='Valeur')  # Classe 'Valeur' avec majuscule

                            if valeur_tag:
                                valeur_text = valeur_tag.get_text(strip=True)

                                # Surface
                                if "surface" in label_text or "carrez" in label_text:
                                    surface_text = valeur_text.replace('m²', '').replace(',', '.')
                                    try:
                                        surface = float(surface_text)
                                    except ValueError:
                                        surface = surface_text

                                # Nombre de Pièces
                                elif "pièce" in label_text or "chambre" in label_text:
                                    try:
                                        nb_pieces = int(valeur_text)
                                    except ValueError:
                                        nb_pieces = valeur_text

                    # --- EXTRACTION ET NETTOYAGE DU PRIX ---
                    prix_tag = soup_detail.find('div', class_='valeur', **{'data-prix-prioritaire': True})
                    if prix_tag:
                        prix_text = prix_tag.get_text(strip=True)
                        prix_nettoye = prix_text.replace('€', '').replace('\xa0', '').replace(' ', '')
                        try:
                            prix = int(prix_nettoye)  # Conversion en nombre entier
                        except ValueError:
                            prix = prix_nettoye  # Garde la chaîne si 'Prix sur demande'
                    else:
                        prix = "N/A"

                    # --- Sauvegarde des données ---
                    all_data.append({
                        'Departement': dept,
                        'URL': link,
                        'Titre': titre,
                        'Type_Bien': type_de_bien,
                        'Localisation': location,
                        'Prix': prix,
                        'Surface_m2': surface,
                        'Nb_Pieces': nb_pieces,
                        'Description': description
                    })

                except Exception as e:
                    continue

except Exception as e:
    print(f"Arrêt du scraping : {e}")

finally:
    # --- 3. Export et Fin ---
    driver.quit()
    df = pd.DataFrame(all_data)
    df.to_csv('annonces_completes_notaires.csv', index=False, encoding='utf-8-sig')
    print("\n--- PROCESSUS TERMINÉ ---")
    print(f"Total des annonces récupérées : {len(df)}")
    print("Fichier 'annonces_completes_notaires.csv' créé avec succès.")