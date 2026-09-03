from pydantic import BaseModel, Field
from typing import Optional, List

class Woning(BaseModel):
    adres: str = Field(description="De straatnaam en het huisnummer")
    prijs: Optional[int] = Field(description="De vraagprijs in euro's (alleen getallen)")
    buurt: str = Field(description="De wijk of buurt in Apeldoorn")
    bouwjaar: Optional[int] = Field(description="Het bouwjaar van de woning")
    kenmerken: List[str] = Field(description="Lijst van belangrijke kenmerken zoals 'glas-in-lood', 'hoge plafonds', 'tuin', 'schuur'")
    match_score: int = Field(description="Score van 1 tot 10 gebaseerd op Willem-Jans wensen")
    motivatie: str = Field(description="Korte uitleg waarom dit huis wel of niet past")
    url: str = Field(description="De directe link naar de woning op de website")

class WoningLijst(BaseModel):
    woningen: List[Woning]