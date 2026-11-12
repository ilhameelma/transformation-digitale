import xml.etree.ElementTree as ET

trips = ET.parse("tripinfo.xml").getroot().findall("tripinfo")
n = len(trips)
duree = sum(float(t.get("duration")) for t in trips) / n
vitesse = sum(float(t.get("routeLength")) / float(t.get("duration")) for t in trips) / n
co2 = sum(float(t.find("emissions").get("CO2_abs")) for t in trips) / 1000  # g
print(f"{n} trajets | durée moy. {duree:.1f} s | vitesse moy. {vitesse*3.6:.1f} km/h | CO2 total {co2:.0f} g")