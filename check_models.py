# Temporary script to find the latest gemini models to use.

import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url).json()

print("Beschikbare Gemini modellen voor tekstgeneratie:\n" + "-"*40)
for model in response.get('models', []):
    # Filter zodat we alleen de modellen zien die tekst kunnen genereren
    if 'generateContent' in model.get('supportedGenerationMethods', []):
        # We knippen 'models/' eraf zodat je precies de naam overhoudt die je nodig hebt
        print(model['name'].replace('models/', ''))