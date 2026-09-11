import os
import requests
import urllib.parse

def find_nearest_supermarket(house_address, api_key):
    # Use the New Places API endpoint
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # The New API requires specific headers, including a FieldMask
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName"
    }
    
    payload = {
        "textQuery": f"supermarket near {house_address}"
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        data = resp.json()
        
        # Check if the response was successful and contains places
        if resp.status_code == 200 and 'places' in data and len(data['places']) > 0:
            place_id = data['places'][0]['id']
            name = data['places'][0]['displayName']['text']
            return f"place_id:{place_id}", name
            
    except Exception as e:
        print(f"⚠️ Error finding supermarket via New Places API: {e}")
        
    return None, None

def bereken_loopafstand(huis_adres, bestemming):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None, None, None
        
    safe_origin = urllib.parse.quote(huis_adres)
    safe_dest = urllib.parse.quote(bestemming)
    
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={safe_origin}&destinations={safe_dest}&mode=walking&key={api_key}"
    
    try:
        resp = requests.get(url, timeout=10).json()
        if resp.get('status') == 'OK':
            element = resp['rows'][0]['elements'][0]
            if element.get('status') == 'OK':
                afstand_tekst = element['distance']['text']
                duur_tekst = element['duration']['text']
                afstand_km = element['distance']['value'] / 1000.0
                return afstand_tekst, duur_tekst, afstand_km
    except Exception as e:
        print(f"⚠️ Error fetching Google Maps API: {e}")
        
    return None, None, None

def evalueer_en_selecteer_locatie(huis_adres, profiel_id):
    """
    Calculates the distance(s) to the center and the nearest supermarket,
    and formats this for the Telegram notification.
    """
    centra_config = {
        "apeldoorn": {"centra": ["Apeldoorn Centrum"], "max_straal": 10.0},
        "harderwijk_ermelo": {"centra": ["Harderwijk Centrum", "Ermelo Centrum"], "max_straal": 7.0}
    }
    
    config = centra_config.get(profiel_id)
    if not config:
        return True, 0.0, 0.0, ""
        
    laagste_afstand_centrum = float('inf')
    centrum_tekst = ""
    
    # 1. Distance to center
    for centrum in config["centra"]:
        _, duur_tekst, afstand_km = bereken_loopafstand(huis_adres, centrum)
        if afstand_km is not None and afstand_km < laagste_afstand_centrum:
            laagste_afstand_centrum = afstand_km
            bestemming_naam = centrum.split()[0]
            centrum_tekst = f"📍 {bestemming_naam}: {afstand_km:.1f} km ({duur_tekst} walking)"
            
    # 2. Distance to nearest supermarket using Places API
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    supermarket_destination, supermarket_name = find_nearest_supermarket(huis_adres, api_key)
    
    supermarkt_tekst = ""
    sm_afstand_km = 0.0
    
    if supermarket_destination:
        # Pass the exact place_id to the distance matrix calculation
        _, sm_duur, sm_afstand_km_result = bereken_loopafstand(huis_adres, supermarket_destination)
        
        if sm_afstand_km_result is not None:
            sm_afstand_km = sm_afstand_km_result
            supermarkt_tekst = f"🛒 Supermarket ({supermarket_name}): {sm_afstand_km:.1f} km ({sm_duur} walking)"

    # Combine for Telegram
    locatie_info_telegram = f"\n{centrum_tekst}"
    if supermarkt_tekst:
        locatie_info_telegram += f"\n{supermarkt_tekst}"

    if laagste_afstand_centrum == float('inf'):
        return True, 0.0, sm_afstand_km, "\n📍 Distance to center: Unknown"
        
    if laagste_afstand_centrum > config["max_straal"]:
        print(f"🛑 Property rejected: too far ({laagste_afstand_centrum:.1f} km, max is {config['max_straal']} km).")
        return False, laagste_afstand_centrum, sm_afstand_km, locatie_info_telegram
        
    return True, laagste_afstand_centrum, sm_afstand_km, locatie_info_telegram

def stuur_telegram_notificatie(adres, score, motivatie, url, regio, profiel_chat_id, locatie_info=""):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = profiel_chat_id if profiel_chat_id and "JOUW_" not in profiel_chat_id else os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return
    
    bericht = f"🌟 <b>Nieuwe Match in {regio}!</b>\n\n🏠 {adres}\n⭐ Score: {score}/10{locatie_info}\n\n💡 {motivatie}\n\n🔗 {url}"
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": bericht, "parse_mode": "HTML"}
    
    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            print(f"📱 ✅ Telegram notification sent for {adres}")
        else:
            print(f"📱 ❌ Error sending Telegram: {response.text}")
    except Exception as e:
        print(f"📱 ❌ Telegram API error: {e}")