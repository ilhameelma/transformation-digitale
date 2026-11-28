import json
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

historique = [
    {"role": "user", "content": "Et si l'avenue Moulay est fermée ?"},
    {"role": "assistant", "content": (
        "Plusieurs rues correspondent. Laquelle ? "
        "Avenue Moulay Ismail (1612,7 m) [avenue-moulay-ismail], "
        "Avenue Moulay Youssef (633,4 m) [avenue-moulay-youssef], "
        "Avenue Moulay Hassan (467,3 m) [avenue-moulay-hassan].")},
]
r = httpx.post("http://localhost:8000/chat", timeout=120,
               json={"question": "Moulay Youssef", "historique": historique})
print("HTTP", r.status_code)
d = r.json()
print(d.get("reponse"))
print("---")
print({k: v for k, v in d.items() if k != "reponse"})