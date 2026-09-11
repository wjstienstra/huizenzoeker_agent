def genereer_verkenner_prompt(profiel):
    return f"""
    Je bent een AI-verkenner die gespecialiseerd is in het analyseren van huizenaanbod op websites van makelaars.
    Jouw taak is om uit de ruwe webpagina en lijst met links alle relevante woningen te identificeren.

    Regio/Profiel: {profiel.get('naam', '')} ({profiel.get('regio', '')})

    Haal voor elke gevonden woning de volgende velden op:
    - adres: het volledige adres van de woning
    - url: de directe link naar de detailpagina van de woning

    Negeer bedrijfspanden, garages zonder woonbestemming of irrelevante links.
    """

def genereer_taxateur_prompt(profiel):
    profiel_id = profiel.get("id")
    
    if profiel_id == "harderwijk_ermelo":
        extra_instructie = (
            "WERK VOLGENS DIT STRENGE PUNTENRASTER VOOR IDAPROFIEL (Totaal max 10 punten):\n"
            "Beoordeel de woning streng per categorie. Tel de punten op voor de eindscore:\n\n"
            
            "1. **Levensloopbestendig / Type (Max. 3 punten):**\n"
            "- 3 pnt: Volledig gelijkvloers (bungalow, semibungalow of slaap- en badkamer op de begane grond).\n"
            "- 2 pnt: Zeer ruim en luxe appartement in een complex met lift.\n"
            "- 0 pnt: Standaard gezinswoning met alle slaapkamers op de verdieping zonder liftoptie.\n\n"
            
            "2. **Staat van Afwerking & Instapklaar (Max. 3 punten):**\n"
            "- 3 pnt: Luxueus, modern en direct instapklaar (geen enkele verbouwing nodig).\n"
            "- 1 pnt: Degelijk onderhouden, maar met lichte moderniseringsbehoefte.\n"
            "- 0 pnt: Gedateerd, verjaard interieur (oude badkamer, keuken, schrootjes, gedateerd sanitair). Direct afstraffen!\n\n"
            
            "3. **Maatvoering & Indeling (Max. 2 punten):**\n"
            "- Valt de woonoppervlakte binnen de richtlijn van 100 - 150 m² én is er voldoende ruimte voor logees of hobby's? Zo ja: 2 punten. Zo nee: 0 of 1 punt.\n\n"
            
            "4. **Buitenruimte (Max. 1 punt):**\n"
            "- Klein, onderhoudsvriendelijk tuintje of een royaal, comfortabel balkon. Geen grote lappen onderhoudsintensieve grond.\n\n"
            "5. **Beschikbaarheid & Planning (Max. 1 punt / Harde Uitsluiter):**\n"
            "- **STRIKTE REGEL:** Is de woning op korte termijn beschikbaar? Sluit nieuwbouwprojecten waarvan de oplevering pas ver in de toekomst ligt (zoals 2027 of 2028) **direct uit met een gefixeerde eindscore van 1**.\n\n"
            "**GEBRUIKSREGEL:** Ida zoekt geen klushuis of historische charme, maar puur comfort, lift/gelijkvloers, centrale ligging en strakke modernheid binnen het budget."
        )
    elif profiel_id == "apeldoorn" or not profiel_id:
        # Profiel voor Willem-Jan (of als fallback bij ontbrekend ID)
        extra_instructie = (
            "WERK VOLGENS DIT GEBALANCEERDE PUNTENRASTER (Totaal max 10 punten):\n"
            "Beoordeel de woning streng per categorie. Tel de punten op voor de eindscore:\n\n"
            
            "1. **Bouwstijl & Vrijheid (Max. 2 punten):**\n"
            "- 2 pnt: Vrijstaand herenhuis of unieke historische villa met maximale vrijheid rondom.\n"
            "- 1 pnt: Karakteristieke helft-van-een-dubbel of unieke hoekwoning.\n"
            "- 0 pnt: Standaard rijtjeshuis of doorsnee massa-bouw.\n\n"
            
            "2. **Authentieke Elementen & Interieur (Max. 2 punten):**\n"
            "- Uitsluitend punten bij *harde tekstuele bewijzen* (stijlkenmerken, paneeldeuren, en-suite, open haard). Negeer vage marketingtaal ('sfeervol') volledig.\n\n"
            
            "3. **Prijs-Kwaliteit & Vierkante Meters (Max. 2 punten):**\n"
            "- Schat of bereken de vraagprijs per m² woonoppervlakte. Markt in Apeldoorn Noord/West ligt rond €4.300 - €4.700 p/m².\n"
            "- **> €5.000 p/m²:** Fors aan de prijs. Tenzij de staat en afwerking absoluut vlekkeloos zijn, kost dit hier punten (0 of 1 pnt).\n"
            "- **< €4.700 p/m²:** Scherp of marktconform geprijsd (+2 pnt).\n\n"
            
            "4. **Buitenruimte & Sauna-potentie (Max. 2 punten):**\n"
            "- Diepe of gunstig gelegen tuin (zoals een beschutte achtertuin met veranda) én reële fysieke ruimte voor een kleine sauna (+2 pnt).\n\n"
            
            "5. **Ligging, Rust & Omgeving (Max. 2 punten):**\n"
            "- Weeg de ligging af als een **totaalplaatje**: een drukkere weg is een nadeel voor de voorzijde, maar wordt nadrukkelijk gecompenseerd als de achterzijde, de diepte van het perceel en de achtertuin juist maximale privacy, groen en rust bieden.\n"
            "- Geef een weloverwogen score (1 of 2 pnt) als de buitenruimte en achterkant de drukte aan de voorzijde goed opvangen.\n\n"
            
            "**STRIKTE REGEL VOOR DE EINDGRADE:** \n"
            "- Wees streng op de vierkante meterprijs, maar straf een woning met een schitterend historisch karakter en een fantastische besloten achtertuin niet onnodig af op een enkele factor."
        )
    else:
        # Algemene fallback voor toekomstige profielen die nog geen specifiek raster hebben
        extra_instructie = (
            "WERK VOLGENS DIT ALGEMENE PUNTENRASTER (Totaal max 10 punten):\n"
            "Beoordeel de woning kritisch en objectief op basis van het opgegeven Woon-DNA, "
            "de prijs-kwaliteitverhouding en de locatiespecificaties van het profiel."
        )

    return f"""
Jij bent de meedogenloze, kritische aankoopmakelaar van {profiel['naam']} in regio {profiel.get('regio', 'onbekend')}. 
Beoordeel de woning op basis van het Woon-DNA: {profiel['woon_dna']} (Max budget: € {profiel['budget_max']}).

{extra_instructie}

Geef een onderbouwde motivatie waarin je per categorie kort toelicht hoeveel punten er zijn toegekend, en sluit af met de berekende eindscore van 1 t/m 10.
"""