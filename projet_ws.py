from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import random
from typing import List, Dict, Any
import re # NOUVEL IMPORT : Expressions régulières
import os 

# --- Configuration ---
BASE_URL = "https://www.etreproprio.com"
SEARCH_URL = BASE_URL + "/annonces/thflcpo.odd.g{page_index}#list"
MAX_PAGES = 30 
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ----------------------------------------------------------------------
# Fonctions Utilitaires
# ----------------------------------------------------------------------

def fetch_page(url: str) -> requests.Response | None:
    """Tente de récupérer le contenu d'une URL, gère les erreurs HTTP."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        time.sleep(random.uniform(1, 3))
        return response
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la récupération de {url}: {e}")
        return None

def extract_listing_links(soup: BeautifulSoup) -> List[str]:
    """Extrait les liens d'annonces de la page de résultats."""
    links = []
    try:
        wrapper = soup.find("div", class_='ep-search-list-wrapper')
        if not wrapper:
            print("⚠️ Avertissement: Wrapper de liste non trouvé sur la page.")
            return links
            
        all_a_tags = wrapper.find_all("a", href=True)
        
        for tag in all_a_tags:
            href = tag['href']
            if href.startswith("/immobilier-"):
                full_url = BASE_URL + href
                links.append(full_url)
            elif href.startswith(BASE_URL + "/immobilier-"):
                 links.append(href)
                 
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des liens : {e}")
        
    return list(set(links))

# ----------------------------------------------------------------------
# Fonctions d'Extraction (Mise à jour pour un nettoyage plus robuste)
# ----------------------------------------------------------------------

def clean_to_float(text: str) -> float:
    """Nettoie la chaîne de caractères pour obtenir un nombre décimal fiable."""
    if not isinstance(text, str):
        return 0.0
        
    # Étape 1: Retire les espaces insécables (&nbsp;), les unités (m²), et les devises (€)
    text = text.replace(u'\xa0', '').replace(' ', '').replace('m²', '').replace('€', '').strip()
    
    # Étape 2: Utilise une expression régulière pour ne garder que les chiffres et les séparateurs décimaux
    # On autorise le point et la virgule, puis on remplace la virgule par un point pour float()
    cleaned_text = re.sub(r'[^\d,.]', '', text)
    cleaned_text = cleaned_text.replace(",", ".")
    
    # Étape 3: Tente la conversion
    try:
        return float(cleaned_text) if cleaned_text else 0.0
    except ValueError:
        return 0.0


def extract_area_details(soup_obj: BeautifulSoup) -> Dict[str, float]:
    """Extrait la surface du bâti et la surface du terrain séparément."""
    
    area_data = {"area_bati": 0.0, "area_terrain": 0.0}
    
    try:
        area_div = soup_obj.find("div", class_='ep-area')
        if not area_div:
            return area_data
        
        # 1. Extraction de la Surface du Terrain (dans le SPAN)
        terrain_span = area_div.find("span", class_='dtl-main-surface-terrain')
        if terrain_span:
            terrain_text = terrain_span.text
            # Nettoyage robuste pour la valeur du terrain
            area_data['area_terrain'] = clean_to_float(terrain_text)
                
        # 2. Extraction de la Surface du Bâti (le nœud de texte principal)
        # Supprimer le SPAN de la soupe temporaire pour isoler le texte du bâti
        if terrain_span:
             terrain_span.decompose() 
        
        # Le texte restant dans la div est la surface du bâti/maison
        bati_text = area_div.text.strip()
        # Nettoyage robuste pour la valeur du bâti
        area_data['area_bati'] = clean_to_float(bati_text)
            
    except Exception as e:
        # En cas d'erreur inattendue (très rare à ce stade), on log l'erreur
        print(f"Erreur lors de l'extraction des surfaces : {e}")
        
    return area_data


def get_text_or_default(soup_obj: BeautifulSoup, class_name: str, default_value: Any = None) -> Any:
    """Fonction utilitaire pour extraire le texte d'une balise div et le nettoyer (pour prix et pièces)."""
    try:
        element = soup_obj.find("div", class_=class_name)
        if element:
            text = element.text.strip()
            
            if class_name == 'ep-price':
                # Utilise clean_to_float pour le prix aussi, car il peut contenir des séparateurs
                return clean_to_float(text)
            elif class_name == 'ep-room':
                # Pour les pièces, on ne veut que l'entier (pas besoin d'expressions régulières si clean_to_float est overkill)
                cleaned_text = ''.join(filter(str.isdigit, text)).strip()
                return cleaned_text if cleaned_text else default_value
            else:
                return text # Pour le titre
        return default_value
    except Exception:
        return default_value


def extract_detail(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extrait l'ensemble des détails d'une page d'annonce."""
    
    # Appel de la fonction spécifique pour les surfaces
    area_results = extract_area_details(soup)

    data = {
        "price": get_text_or_default(soup, 'ep-price', 0), # Prix est maintenant float après clean_to_float
        "title": get_text_or_default(soup, 'ep-title', ""),
        "area_bati": area_results["area_bati"],
        "area_terrain": area_results["area_terrain"],
        "room": get_text_or_default(soup, 'ep-room', 0),
    }

    # Tentative de conversion finale pour price et room (room uniquement)
    try:
        data['room'] = int(data['room']) if data['room'] else 0
    except ValueError:
        data['room'] = 0
        
    return data

# ----------------------------------------------------------------------
# Fonction Principale
# ----------------------------------------------------------------------

def main():
    """Fonction principale pour orchestrer le scraping."""
    
    all_data: List[Dict[str, Any]] = []
    
    for page_index in range(MAX_PAGES):
        list_url = SEARCH_URL.format(page_index=page_index)
        print(f"🔎 Traitement de la page {page_index + 1}/{MAX_PAGES}: {list_url}")
        
        page_response = fetch_page(list_url)
        if not page_response:
            continue
            
        list_soup = BeautifulSoup(page_response.content, 'html.parser')
        listing_links = extract_listing_links(list_soup)
        
        print(f"    - {len(listing_links)} annonces trouvées.")
        
        for link in listing_links:
            detail_response = fetch_page(link)
            if not detail_response:
                continue
                
            detail_soup = BeautifulSoup(detail_response.content, 'html.parser')
            announcement_data = extract_detail(detail_soup)
            
            # Affichage console mis à jour
            print(f"      -> Prix: {announcement_data['price']:,.0f}€, Bâti: {announcement_data['area_bati']:.1f}m², Terrain: {announcement_data['area_terrain']:.1f}m², Pièces: {announcement_data['room']}")
            
            all_data.append(announcement_data)

    if all_data:
        df = pd.DataFrame(all_data)
        output_file = "annonces_scrapees.xlsx"
        
        df.to_excel(output_file, index=False)
        print("\n✅ Scraping terminé !")
        print(f"💾 Fichier créé : {output_file} ({len(df)} lignes)")
    else:
        print("\n😔 Aucun donnée n'a été extraite. Le site a peut-être bloqué l'accès ou la structure a changé.")

if __name__ == "__main__":
    main()
