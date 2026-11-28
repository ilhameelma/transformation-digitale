"""API du chatbot : POST /chat, GET /scenario/{street_id}, GET /health."""
import os
import sys

sys.path.insert(0, "chat-api")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import outils_scenario as scen
from chatbot import repondre

app = FastAPI(title="Jumeau numérique : chatbot")

# la vue 3D (React, Vite ou Nginx) appelle l'API depuis le navigateur
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS",
                            "http://localhost:5173,http://localhost:5174").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")   # jamais "system" ni "tool"
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    historique: list[Message] = []


@app.get("/health")
def health():
    return {"statut": "ok"}


@app.get("/scenario/{street_id}")
def scenario(street_id: str):
    """État d'une rue, sans LLM : la vue 3D l'interroge toutes les 3 s."""
    res = scen.get_scenario(street_id)
    if res["statut"] == "rue_inconnue":
        raise HTTPException(status_code=404, detail="rue inconnue")
    return res


@app.post("/chat")
def chat(req: ChatRequest):
    historique = [m.model_dump() for m in req.historique[-6:]]
    try:
        return repondre(req.question, historique)
    except Exception as e:
        print("ERREUR /chat :", type(e).__name__, e)   # détail dans le terminal seulement
        raise HTTPException(status_code=503,
                            detail="Le modèle de langage n'est pas disponible. Réessaie plus tard.")