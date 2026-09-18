import os
import json
import re
from urllib.parse import urlparse, urlunparse

MEMORY_FILE = "huizen_gezien.json"

def laad_profielen():
    if not os.path.exists('profielen.json'):
        print("❌ Kan profielen.json niet vinden. Zorg dat het bestand bestaat.")
        return []
    try:
        with open('profielen.json', 'r', encoding='utf-8') as f:
            profielen = json.load(f)
            # Filter op actieve profielen indien de vlag aanwezig is
            return [p for p in profielen if p.get("actief", True)]
    except Exception as e:
        print(f"⚠️ Fout bij het inlezen van profielen.json: {e}")
        return []

def laad_geheugen():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Fout bij het inlezen van geheugen ({MEMORY_FILE}): {e}")
            return {}
    return {}

def sla_geheugen_op(geheugen):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(geheugen, f, indent=4)

def sanitize_url(url: str) -> str:
    """Stript query parameters, fragments and trailing slashes from URLs."""
    if not url:
        return ""
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip('/')
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, '', '', '')).lower()

def normaliseer_adres(adres: str) -> str:
    """Normaliseert een adres naar kleine letters, zonder leestekens en overtollige spaties.
    
    Verwijdert ook Nederlandse postcodes (4 cijfers + 2 letters) zodat verschillen
    in wel/geen postcode-notatie matchen.
    """
    if not adres:
        return ""
    tekst = adres.lower()
    # Verwijder Nederlandse postcode patronen (bv '3851 xh' of '3851xh')
    tekst = re.sub(r'\b\d{4}\s*[a-z]{2}\b', '', tekst)
    # Verwijder alle leestekens behalve alfanumeriek
    tekst = re.sub(r'[^a-z0-9\s]', ' ', tekst)
    # Breng meervoudige spaties terug naar enkele spatie
    return " ".join(tekst.split())

def is_woning_bekend(url: str, adres: str, profiel_geheugen: dict) -> bool:
    """Controleert of een woning al voorkomt in het profielgeheugen op basis van

    zowel een opgeschoonde URL als een genormaliseerd adres.
    """
    if not url and not adres:
        return True

    clean_check_url = sanitize_url(url)
    norm_check_adres = normaliseer_adres(adres)

    # 1. Directe URL match of opgeschoonde URL match
    if url in profiel_geheugen or clean_check_url in profiel_geheugen:
        return True

    for opgeslagen_url, data in profiel_geheugen.items():
        # Vergelijk opgeschoonde versies van de URL-sleutels
        if clean_check_url and sanitize_url(opgeslagen_url) == clean_check_url:
            return True

        # 2. Inhoudelijke adresmatch
        opgeslagen_adres = data.get("adres", "")
        if norm_check_adres and opgeslagen_adres:
            if normaliseer_adres(opgeslagen_adres) == norm_check_adres:
                return True

    return False