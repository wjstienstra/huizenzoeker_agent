import os
import json

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