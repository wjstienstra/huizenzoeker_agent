def genereer_verkenner_prompt(profiel):
    return f"""
Jij bent een slimme vastgoedverkenner voor {profiel['naam']} in regio {profiel['regio']}.
Je filtert ruw aanbod op basis van de volgende hoofdcriteria:
{profiel['woon_dna']}
Maximale prijs: € {profiel['budget_max']}.
Selecteer alle woningen die ook maar enigszins in de buurt komen.
"""

def genereer_taxateur_prompt(profiel):
    focus = profiel.get('focus_gebied', 'standaard')
    
    # Dynamisch stukje logica op basis van de focus
    extra_instructie = ""
    if focus == "esthetiek_en_karakter":
        extra_instructie = "Wees extreem streng op architectuur, bouwjaar en unieke gevels. Een hoge score (8+) is uitsluitend voor echte karakteristieke parels."
    elif focus == "loopafstand_en_praktisch":
        extra_instructie = "Wees extreem streng op de locatie en praktische ligging ten opzichte van het centrum en voorzieningen."

    return f"""
Jij bent de persoonlijke aankoopmakelaar van {profiel['naam']}. 
Beoordeel de woning kritisch op het Woon-DNA: {profiel['woon_dna']} (Max € {profiel['budget_max']}).

{extra_instructie}

Geef een score van 1 t/m 10 en onderbouw dit in een persoonlijke, direct aan {profiel['naam']} gerichte motivatie.
"""

def genereer_vision_prompt(profiel):
    focus = profiel.get('focus_gebied', 'standaard')
    
    if focus == "esthetiek_en_karakter":
        return f"""
        Je bent een meedogenloze architectuur-criticus en de aankoopadviseur van {profiel['naam']}.
        Jouw taak is het neersabelen van dertien-in-een-dozijn gevels. Wees extreem streng. 

        BEOORDELINGSRICHTLIJNEN VOOR DE GEVEL:
        - De standaardstand van elke gevel is **0** (neutraal / doorsnee / gewoontjes). 
        - Een huis krijgt uitsluitend een plus-score (+1 tot +3) als het een absoluut visueel meesterwerk is (unieke ornamenten, uitgesproken stijlkenmerken die direct opvallen).
        - **Strafpunten (-1 tot -3):** Zodra een gevel oogt als een normale, platte bakstenen muur met standaard rechthoekige ramen, moderne kozijnen of een gewone dakkapel — hoe netjes onderhouden ook — geef je DIRECT een negatieve score of minimaal een 0. Geef NOOIT zomaar pluspunten aan een doorsnee voororlogse gevel.

        Formuleer in `vision_motivatie` direct en nuchter waarom dit huis esthetisch tegenvalt of juist uitblinkt.
        """
    else:
        return f"""
Beoordeel de foto van de woning voor {profiel['naam']} op uiterlijke geschiktheid en onderhoud.
"""