"""Chatbot complet : 5 outils + boucle d'outils.
Réutilise chatbot_test.py (client, modèle, prompt, vérification des chiffres)."""
import json
import os
import sys

sys.path.insert(0, os.path.join("chat-api", "rag"))
sys.path.insert(0, "chat-api")

from chatbot_test import (client, MODEL, SYSTEM_PROMPT, verifier_chiffres,
                          executer_outil as executer_search)
from search_docs import TOOL_NAME, TOOL_DESCRIPTION, TOOL_PARAMETERS
from resolve_street import resolve_street
import outils_scenario as scen

SYSTEM_PROMPT_COMPLET = SYSTEM_PROMPT + """

Règles supplémentaires pour les rues (elles complètent les règles 1 à 13) :
14. Exception à la règle 1 : pour une question sur une rue précise (« et si la rue X est fermée ? »), appelle d'abord resolve_street avec le texte de la rue, pas search_docs.
15. Si resolve_street renvoie « ambigu », pose une question courte : liste les candidats avec leur nom, leur longueur en mètres et leur street_id entre crochets, et n'appelle aucun autre outil. Si « introuvable », dis que cette rue n'est pas dans l'index, sans rien inventer.
16. Si resolve_street renvoie « trouve », regarde le champ scenario. « ready » : appelle get_kpi avec le street_id. « missing » ou « failed » : appelle trigger_simulation, puis dis que le calcul est lancé et dure environ une minute, sans donner de résultat. « running » : dis que le calcul est en cours.
17. Si l'utilisateur répond à ta question en choisissant un candidat, utilise son street_id directement avec get_scenario, sans rappeler resolve_street.
18. N'invente jamais de street_id : utilise seulement ceux renvoyés par resolve_street ou listés dans ta question précédente.
19. Pour les chiffres d'une rue, get_kpi prime sur search_docs. Pour une rue fermée, dis « tirage 1, résultat indicatif ». Si comparaison_reseau_fiable vaut false, ne donne aucun verdict sur l'ensemble du réseau. Utilise les champs de impact (voitures_concernees, deviees, sans_itineraire, comparables, durées) et le nom de rue renvoyé par l'outil.
20. Si un outil renvoie une erreur ou airflow_indisponible, dis-le simplement, sans réessayer.
21. Cite comme source uniquement le champ « source » renvoyé par l'outil, jamais un autre nom de fichier."""


def _outil(nom, description, proprietes, requis):
    return {"type": "function", "function": {
        "name": nom, "description": description,
        "parameters": {"type": "object", "properties": proprietes, "required": requis}}}


TOOLS = [
    {"type": "function", "function": {
        "name": TOOL_NAME, "description": TOOL_DESCRIPTION,
        "parameters": TOOL_PARAMETERS}},
    _outil("resolve_street",
           "Trouve une rue dans l'index à partir d'un texte libre. Renvoie trouve (avec street_id et l'état du scénario), ambigu (candidats) ou introuvable.",
           {"texte": {"type": "string", "description": "Nom de la rue comme écrit par l'utilisateur"}},
           ["texte"]),
    _outil("get_scenario",
           "Donne l'état du scénario rue fermée d'une rue : ready, running, failed ou missing.",
           {"street_id": {"type": "string"}}, ["street_id"]),
    _outil("trigger_simulation",
           "Lance le calcul du scénario rue fermée d'une rue dont l'état est missing ou failed.",
           {"street_id": {"type": "string"}}, ["street_id"]),
    _outil("get_kpi",
           "Lit les indicateurs exacts : d'une rue fermée (street_id) ou d'un scénario global (scenario, par exemple pic).",
           {"street_id": {"type": "string"}, "scenario": {"type": "string"}}, []),
]


def executer_outil(nom, args):
    try:
        if nom == TOOL_NAME:
            return executer_search(nom, args)
        if nom == "resolve_street":
            res = resolve_street(str(args.get("texte", "")))
            if res["statut"] == "trouve":   # économise une requête LLM
                res["scenario"] = scen.get_scenario(res["street_id"])["statut"]
            return res
        if nom == "get_scenario":
            return scen.get_scenario(str(args.get("street_id", "")))
        if nom == "trigger_simulation":
            return scen.trigger_simulation(str(args.get("street_id", "")))
        if nom == "get_kpi":
            return scen.get_kpi(street_id=args.get("street_id"),
                                scenario=args.get("scenario"))
        return {"erreur": f"outil inconnu : {nom}"}
    except Exception as e:
        return {"erreur": f"{type(e).__name__}: {e}"}


def _suivre(nom, res, rue):
    """Mémorise la rue et son état, pour que la vue 3D sache quoi afficher."""
    if nom == "resolve_street" and res.get("statut") == "trouve":
        rue.update(street_id=res["street_id"], statut=res["scenario"])
    elif nom == "get_scenario" and res.get("statut") != "rue_inconnue":
        rue.update(street_id=res["street_id"], statut=res["statut"])
    elif nom == "trigger_simulation" and res.get("statut") in ("lance", "deja_en_cours"):
        rue.update(street_id=res["street_id"], statut="running")


def repondre(question, historique=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT_COMPLET}]
    messages += historique or []
    messages.append({"role": "user", "content": question})
    sorties, rue = [], {}

    for _ in range(6):  # garde-fou : 6 tours d'outils maximum
        rep = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, temperature=0)
        msg = rep.choices[0].message
        if not msg.tool_calls:
            texte = msg.content or ""
            return {"reponse": texte,
                    "suspects": verifier_chiffres(texte, sorties), **rue}
        messages.append(msg)
        for appel in msg.tool_calls:
            args = json.loads(appel.function.arguments or "{}")
            res = executer_outil(appel.function.name, args)
            _suivre(appel.function.name, res, rue)
            texte = json.dumps(res, ensure_ascii=False, default=str)
            sorties.append(texte)
            messages.append({"role": "tool", "tool_call_id": appel.id,
                             "content": texte})
    return {"reponse": "Je n'ai pas pu répondre.", "suspects": [], **rue}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Et si l'avenue Moulay Youssef est fermée ?"
    try:
        r = repondre(q)
    except Exception as e:
        print("ERREUR :", e)
        sys.exit(1)
    print(r["reponse"])
    if r.get("street_id"):
        print("\n[3D]", r["street_id"], r["statut"])
    if r["suspects"]:
        print("[ALERTE] Nombres absents des résultats d'outils :", r["suspects"])