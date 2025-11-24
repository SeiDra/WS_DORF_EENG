from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import random
from typing import List, Dict, Any

# --- Configuration ---
BASE_URL = "https://www.etreproprio.com"
SEARCH_URL = BASE_URL + "/annonces/thflcpo.odd.g{page_index}#list"
MAX_PAGES = 30
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_page(url: str) -> requests.Response | None:
    """Tente de récupérer le contenu d'une URL, gère les erreurs HTTP."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()  # Lance une exception pour les codes d'erreur 4xx/5xx
        time.sleep(random.uniform(1, 3))  # Délai aléatoire pour respecter le serveur
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
            
        # Trouver tous les liens dans le wrapper
        all_a_tags = wrapper.find_all("a", href=True)
        
        # Filtrer les liens qui correspondent au format d'une annonce immobilière
        for tag in all_a_tags:
            href = tag['href']
            if href.startswith("/immobilier-"):
                full_url = BASE_URL + href
                links.append(full_url)
            elif href.startswith(BASE_URL + "/immobilier-"):
                 links.append(href)
                 
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des liens : {e}")
        
    # Utilisation d'un set pour garantir l'unicité des liens avant de retourner
    return list(set(links))

def extract_detail(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extrait les détails (prix, titre, surface, pièces) d'une page d'annonce."""
    
    # Fonction utilitaire pour extraire le texte et nettoyer
    def get_text_or_default(soup_obj: BeautifulSoup, class_name: str, default_value: Any = None) -> Any:
        try:
            # On cherche directement le texte de l'élément sans utiliser .text.replace(" ", "")
            # qui peut retirer des espaces importants (sauf pour les nombres)
            element = soup_obj.find("div", class_=class_name)
            if element:
                 # Nettoyage spécifique pour les valeurs numériques
                text = element.text.strip()
                if class_name in ['ep-price', 'ep-area']:
                    # Retire les espaces, devises (€), unités (m², etc.) et garde les chiffres/points
                    return ''.join(filter(lambda x: x.isdigit() or x in '.,', text)).replace(",", ".").strip()
                elif class_name in ['ep-room']:
                    # Retire tout sauf les chiffres
                    return ''.join(filter(str.isdigit, text)).strip()
                else:
                    return text # Pour le titre
            return default_value
        except Exception:
            return default_value

    data = {
        "price": get_text_or_default(soup, 'ep-price', 0),
        "title": get_text_or_default(soup, 'ep-title', ""),
        "area": get_text_or_default(soup, 'ep-area', 0),
        "room": get_text_or_default(soup, 'ep-room', 0),
    }

    # Tentative de conversion numérique (car les valeurs sont des chaînes après extraction)
    try:
        data['price'] = float(data['price']) if data['price'] else 0.0
    except ValueError:
        data['price'] = 0.0
        
    try:
        data['area'] = float(data['area']) if data['area'] else 0.0
    except ValueError:
        data['area'] = 0.0
        
    try:
        data['room'] = int(data['room']) if data['room'] else 0
    except ValueError:
        data['room'] = 0
        
    return data

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
            print(f"    - Récupération des détails : {link}")
            detail_response = fetch_page(link)
            if not detail_response:
                continue
                
            detail_soup = BeautifulSoup(detail_response.content, 'html.parser')
            announcement_data = extract_detail(detail_soup)
            
            # Affichage console pour vérification immédiate
            print(f"      -> Prix: {announcement_data['price']}, Surface: {announcement_data['area']}, Pièces: {announcement_data['room']}")
            
            all_data.append(announcement_data)

    if all_data:
        # Création et enregistrement du DataFrame
        df = pd.DataFrame(all_data)
        output_file = "annonces_scrapees.xlsx"
        df.to_excel(output_file, index=False)
        print("\n✅ Scraping terminé !")
        print(f"💾 Fichier créé : {output_file} ({len(df)} lignes)")
    else:
        print("\n😔 Aucun donnée n'a été extraite. Le site a peut-être bloqué l'accès ou la structure a changé.")

if __name__ == "__main__":
    main()
