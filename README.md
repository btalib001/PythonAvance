# 🏠 Analyse du Marché Immobilier via Web Scraping

## 📋 Présentation du Projet

Ce projet consiste à automatiser la collecte et l'analyse de données immobilières provenant du site **immobilier.notaires.fr**. L'objectif est de comprendre les dynamiques de prix au mètre carré en fonction de la localisation et des caractéristiques des biens.

## 🚀 Objectifs

* 
**Collecte automatisée** : Extraction des données (prix, surface, type de bien, localisation).

* 
**Traitement de données** : Nettoyage et structuration avec Python.

* 
**Analyse Statistique** : Calcul des moyennes, médianes et corrélations entre surface et prix.

* 
**Visualisation** : Création d'un tableau de bord interactif pour explorer les données.



## 🛠️ Stack Technique

| Étape | Outils / Librairies |
| --- | --- |
| **Scraping** | <br>`requests`, `BeautifulSoup`, `re` (regex) 

 |
| **Data Manipulation** | <br>`pandas`, `numpy` 

 |
| **Géolocalisation** | <br>`geopy`, API OpenStreetMap 

 |
| **Visualisation** | <br>`matplotlib`, `seaborn`, `plotly` 

 |
| **Dashboard** | <br>`Streamlit` 

 |

## 🏗️ Architecture du Repo

* 
`src/scraper.py` : Script de récupération des données.

* 
`src/clean_data.py` : Nettoyage, suppression des doublons et normalisation.

* 
`src/analysis.py` : Calculs statistiques et génération de graphiques.

* 
`src/dashboard.py` : Interface utilisateur Streamlit.

* 
`notebooks/exploration.ipynb` : Analyse exploratoire (EDA).

* 
`data/` : Dossier contenant les fichiers CSV (données brutes et nettoyées).



## 📊 Fonctionnalités du Dashboard

L'application **Streamlit** permet de :

1. 
**Filtrer** les biens par ville, prix ou surface.


2. Visualiser la **répartition des prix** via des histogrammes et boxplots.


3. Afficher une **carte interactive** des annonces grâce à `folium`.


---

## 📈 Perspectives d'amélioration

* Mise en place d'un **scheduling automatique** (cron) pour actualiser les prix chaque semaine.

* Développement d'un module de **Machine Learning** (régression linéaire) pour prédire le prix d'un bien.

Souhaites-tu que je t'aide à rédiger la section **"Résultats et Analyses"** avec des exemples de conclusions statistiques, ou veux-tu que l'on peaufine le **script de nettoyage**  pour gérer les données manquantes ?
