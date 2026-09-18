import os
import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from models import WoningLijst, Woning, VisionBeoordeling

# Provider initialisatie
provider = GoogleProvider(api_key=os.getenv('GEMINI_API_KEY'))

CASCADE_MODELS = [
    'gemini-pro-latest',
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite'
]

# Module-level set to keep track of models that ran out of quota during the execution
UITGESCHAKELDE_MODELS = set()

def reset_cascade_state():
    """Clears the disabled models set so the cascade starts fresh on the next run."""
    global UITGESCHAKELDE_MODELS
    UITGESCHAKELDE_MODELS.clear()
    print("🔄 Cascade-status gereset: alle modellen weer beschikbaar.")

# --- DE CASCADE RUNNER ---
async def cascade_run(agent_factory, system_prompt, user_prompt):
    last_error = None
    for model_naam in CASCADE_MODELS:
        # Sla modellen over die eerder in deze run al een quota-fout gaven
        if model_naam in UITGESCHAKELDE_MODELS:
            continue

        model = GoogleModel(model_naam, provider=provider)
        agent = agent_factory(model, system_prompt)
        retries, max_retries, wachttijd = 0, 2, 2
        
        print(f"🤖 Poging met model: {model_naam}...")
        while retries <= max_retries:
            try:
                return await agent.run(user_prompt)
            except Exception as e:
                err = str(e).lower()
                if any(msg in err for msg in ["503", "high demand", "unavailable"]):
                    retries += 1
                    await asyncio.sleep(wachttijd)
                    wachttijd *= 2
                    continue
                elif "429" in err or "quota" in err:
                    print(f"   🚫 Quota bereikt voor {model_naam}. Model uitgeschakeld voor deze run.")
                    UITGESCHAKELDE_MODELS.add(model_naam)
                    break 
                else: 
                    raise e
        last_error = f"Laatste actieve model {model_naam} faalde."

    raise Exception(f"Model Cascade volledig uitgeput. {last_error}")

# --- AGENT FACTORIES ---
def get_verkenner(model, system_prompt):
    return Agent(model, output_type=WoningLijst, system_prompt=system_prompt)

def get_taxateur(model, system_prompt):
    return Agent(model, output_type=Woning, system_prompt=system_prompt)

def get_vision_agent(model, system_prompt):
    return Agent(model, output_type=VisionBeoordeling, system_prompt=system_prompt)