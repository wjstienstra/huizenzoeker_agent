import os
import requests
import urllib.parse

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
                duur_minuten = element['duration']['value'] / 60
                return afstand_tekst, duur_tekst, duur_minuten
    except Exception as e:
        print(f"⚠️ Fout bij ophalen Google Maps API: {e}")
        
    return None, None, None


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
            print(f"📱 ✅ Telegram notificatie verstuurd voor {adres}")
        else:
            print(f"📱 ❌ Fout bij versturen Telegram: {response.text}")
    except Exception as e:
        print(f"📱 ❌ Telegram API error: {e}")