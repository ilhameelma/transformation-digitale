import json
import os
import re
import sys

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.join("chat-api", "rag"))
from search_docs import search_docs, TOOL_NAME, TOOL_DESCRIPTION, TOOL_PARAMETERS

load_dotenv()
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    max_retries=6,
    timeout=60,
)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """Tu es l'assistant du jumeau numérique 3D de mobilité urbaine (Rabat centre).
Tu réponds en français, de façon simple.

Règles obligatoires :
1. Pour toute question sur le projet (explications, hypothèses, limites, résultats), appelle d'abord l'outil search_docs.
2. Réponds UNIQUEMENT à partir des extraits retournés par les outils. N'utilise aucune connaissance générale sur Rabat, le trafic, la météo ou autre.
3. Ne cite AUCUN chiffre qui ne figure pas dans un résultat d'outil de cette conversation. Ne calcule pas de nouveaux chiffres.
4. Pour chaque chiffre cité, précise le scénario, la référence de comparaison et le nombre de trajets terminés si les extraits les donnent. Ne compare jamais deux scénarios dont les références diffèrent.
5. Si deux extraits se contredisent, signale la contradiction au lieu de choisir.
6. Si search_docs renvoie "aucun_resultat" ou des extraits qui ne contiennent pas l'information, réponds exactement : « Je n'ai pas cette information dans les documents du projet. »
7. N'affirme pas un gain ou une perte si l'écart n'est pas net ou vient d'un seul tirage : dis que le résultat est indicatif. Pour la rue fermée, rappelle le biais de sélection.
8. Termine toute réponse qui contient un chiffre ou un résultat par : « Données simulées (SUMO). » et cite le fichier source.
9. Si la question n'a aucun rapport avec le jumeau numérique, refuse poliment.
10. Réponds en 8 lignes maximum, sans titres ni tableaux. Commence par la réponse directe, puis donne au plus 3 chiffres utiles, avec leur scénario et leur référence. Ne détaille d'autres chiffres que si on te le demande.
11. Pour une question « est-ce que X améliore ou dégrade Y ? » : ne réponds jamais simplement « oui » ou « non ». Dis ce que les documents montrent (« gain net démontré », « pas de gain net démontré » ou « résultat indicatif ») et pourquoi, avec la source.
12. N'ajoute aucune explication causale (« à cause de », « explique ») qui ne figure pas explicitement dans un extrait retourné.
13. Si la référence d'un scénario est absente, ou si les trajets terminés diffèrent de plus de 2 % entre le scénario et sa référence, ne donne aucun écart ni verdict : dis qu'aucune comparaison fiable n'est possible, et explique pourquoi. Si deux sources donnent des chiffres différents pour le même indicateur, cite les deux avec leur fichier et ne tranche pas."""

TOOLS = [{
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "parameters": TOOL_PARAMETERS,
    },
}]


def executer_outil(nom, arguments):
    if nom != TOOL_NAME:
        return {"erreur": f"outil inconnu : {nom}"}
    # on ne garde que les paramètres connus, et "type" -> "type_"
    if "type" in arguments:
        arguments["type_"] = arguments.pop("type")
    autorises = {"question", "scenario", "type_"}
    arguments = {k: v for k, v in arguments.items() if k in autorises}
    return search_docs(**arguments)


def verifier_chiffres(reponse, sorties_outils):
    """Test T11 simplifié : signale les nombres absents des résultats d'outils."""
    reponse = re.sub(r"\b3\s?D\b", "", reponse)  # "3D" n'est pas un chiffre de résultat
    source = " ".join(sorties_outils).replace(",", ".")
    suspects = []
    for n in re.findall(r"\d+(?:[.,]\d+)?", reponse):
        if n.replace(",", ".") not in source:
            suspects.append(n)
    return suspects


def repondre(question, historique=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += historique or []
    messages.append({"role": "user", "content": question})
    sorties_outils = []

    for _ in range(4):  # garde-fou : 4 tours d'outils maximum
        rep = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, temperature=0
        )
        msg = rep.choices[0].message
        if not msg.tool_calls:
            suspects = verifier_chiffres(msg.content or "", sorties_outils)
            return msg.content, suspects
        messages.append(msg)
        for appel in msg.tool_calls:
            args = json.loads(appel.function.arguments)
            resultat = executer_outil(appel.function.name, args)
            texte = json.dumps(resultat, ensure_ascii=False, default=str)
            sorties_outils.append(texte)
            messages.append({
                "role": "tool",
                "tool_call_id": appel.id,
                "content": texte,
            })
    return "Je n'ai pas pu répondre.", []


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Pourquoi les bus attendent autant ?"
    try:
        texte, suspects = repondre(q)
    except Exception as e:
        print("ERREUR :", e)
        corps = getattr(getattr(e, "response", None), "text", None)
        if corps:
            print("DÉTAIL :", corps)
        sys.exit(1)
    print(texte)
    if suspects:
        print("\n[ALERTE] Nombres absents des résultats d'outils :", suspects)