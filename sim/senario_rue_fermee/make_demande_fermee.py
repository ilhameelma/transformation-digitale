"""Etape 2 : demande du scenario rue fermee.

La demande de reference (../hassan.rou.xml, 300 vehicules) n'est jamais modifiee. Pour le scenario, seuls les
vehicules dont l'itineraire passait par la rue fermee sont re-routes (duarouter, reseau ferme) ; tous les autres
gardent exactement leur itineraire. L'effet mesure est donc bien celui de la fermeture.
Un vehicule dont le depart ou l'arrivee est sur la rue fermee n'a plus d'itineraire : il est retire (compte).

Ecrit : runs/rue_fermee.rou.xml, runs/rue_fermee_demande.json
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

from common import (NET_FERME, ROU_FERME, ROU_REF, RUNS, exiger, route_de, troncons_fermes)


def main():
    exiger("duarouter")
    if not NET_FERME.exists():
        sys.exit("Lancer d'abord make_rue_fermee.py")
    RUNS.mkdir(exist_ok=True)
    fermes = set(troncons_fermes())

    tree = ET.parse(ROU_REF)
    root = tree.getroot()
    touches = []
    for v in root.findall("vehicle"):
        e = route_de(v)
        if fermes & set(e):
            touches.append((v.get("id"), v.get("depart"), e[0], e[-1]))

    trips = RUNS / "touches.trips.xml"
    trips.write_text("<routes>\n" + "".join(
        f'    <trip id="{i}" depart="{d}" from="{a}" to="{b}"/>\n' for i, d, a, b in touches) + "</routes>\n",
        encoding="utf-8")
    sortie = RUNS / "touches.rou.xml"
    subprocess.run(["duarouter", "-n", str(NET_FERME), "--route-files", str(trips), "-o", str(sortie),
                    "--ignore-errors", "--no-warnings", "--no-step-log"], check=True)

    nouveaux = {v.get("id"): route_de(v) for v in ET.parse(sortie).getroot().iter("vehicle")}
    ids_touches = {t[0] for t in touches}
    deviees = retires = 0
    for v in list(root.findall("vehicle")):
        vid = v.get("id")
        if vid not in ids_touches:
            continue
        if vid in nouveaux and nouveaux[vid]:
            r = v.find("route")
            r.set("edges", " ".join(nouveaux[vid]))
            for k in ("cost", "savings"):
                r.attrib.pop(k, None)
            deviees += 1
        else:
            root.remove(v)
            retires += 1
    tree.write(ROU_FERME, encoding="utf-8", xml_declaration=True)

    info = {"vehicules_reference": len(root.findall("vehicle")) + retires,
            "voitures_sur_la_rue_fermee": len(touches), "deviees": deviees, "sans_itineraire": retires,
            "ids_concernees": sorted(ids_touches, key=int)}
    (RUNS / "rue_fermee_demande.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(touches)} voitures passaient par la rue fermee : {deviees} deviees, {retires} sans itineraire")
    print(f"-> {ROU_FERME}")


if __name__ == "__main__":
    main()