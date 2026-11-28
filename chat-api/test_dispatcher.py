import json
import sys

sys.path.insert(0, "chat-api")
from chatbot import executer_outil


def p(n, nom, args):
    print(n, nom, json.dumps(executer_outil(nom, args), ensure_ascii=False)[:300])


p(1, "resolve_street", {"texte": "allal ben abdellah"})
p(2, "resolve_street", {"texte": "avenue moulay"})
p(3, "resolve_street", {"texte": "rue de la pizza"})
p(4, "get_scenario", {"street_id": "avenue-annasr"})
p(5, "get_kpi", {"street_id": "avenue-annasr"})
p(6, "trigger_simulation", {"street_id": "avenue-annasr"})
p(7, "trigger_simulation", {"street_id": "x; rm -rf"})
p(8, "outil_inconnu", {})
p(9, "get_kpi", {})
p(10, "search_docs", {"question": "pourquoi les bus attendent autant ?"})