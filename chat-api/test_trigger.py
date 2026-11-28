import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
modele = sys.argv[1] if len(sys.argv) > 1 else os.getenv("OPENAI_MODEL")
print("Modèle testé :", repr(modele))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
                max_retries=0, timeout=60)   # un seul essai

t = time.time()
try:
    r = client.chat.completions.create(
        model=modele,
        messages=[{"role": "user", "content": "Dis bonjour en 3 mots."}])
    print(f"Réponse en {time.time()-t:.1f} s :", r.choices[0].message.content)
except Exception as e:
    print(f"ERREUR après {time.time()-t:.1f} s :", type(e).__name__, e)