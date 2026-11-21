import sys
import xml.etree.ElementTree as ET

def kpi(fichier):
    trips = ET.parse(fichier).getroot().findall("tripinfo")
    n = len(trips)
    duree = sum(float(t.get("duration")) for t in trips) / n
    vitesse = sum(float(t.get("routeLength")) / float(t.get("duration")) for t in trips) / n * 3.6
    attente = sum(float(t.get("waitingTime")) for t in trips) / n
    perdu = sum(float(t.get("timeLoss")) for t in trips) / n
    co2 = sum(float(t.find("emissions").get("CO2_abs")) for t in trips) / 1000
    return n, duree, vitesse, attente, perdu, co2

noms = ["trajets terminés", "durée moy. (s)", "vitesse moy. (km/h)",
        "attente moy. (s)", "temps perdu moy. (s)", "CO2 total (g)"]
a = kpi(sys.argv[1])
b = kpi(sys.argv[2])

print(f"{'indicateur':<24}{'actuel':>12}{'voie réservée':>15}")
for nom, x, y in zip(noms, a, b):
    print(f"{nom:<24}{x:>12.1f}{y:>15.1f}")