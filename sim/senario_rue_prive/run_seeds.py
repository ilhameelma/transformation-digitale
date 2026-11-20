import os
import subprocess
import statistics
import xml.etree.ElementTree as ET

AXE = {"4330541#3", "4330541#7", "4330541#9", "4330541#10",
       "4330541#11", "4330541#12", "4330541#15", "4330541#18"}
SEEDS = range(1, 11)
FIN = 1500
SCEN = {"actuel": "../hassan.net.xml", "reservee": "hassan_voie_reservee_v2.net.xml"}

os.makedirs("runs", exist_ok=True)

ids_axe = set()
for _, el in ET.iterparse("../hassan.rou.xml", events=("end",)):
    if el.tag == "vehicle":
        r = el.find("route")
        if r is not None and r.get("edges") and any(e in AXE for e in r.get("edges").split()):
            ids_axe.add(el.get("id"))
        el.clear()

def lance(nom, net, seed):
    sortie = f"runs/tripinfo_{nom}_{seed}.xml"
    subprocess.run(["sumo", "-n", net, "-r", "../hassan.rou.xml", "-b", "0", "-e", str(FIN),
                    "--seed", str(seed), "--tripinfo-output", sortie,
                    "--device.emissions.probability", "1",
                    "--no-step-log", "true", "--no-warnings", "true"],
                   check=True, stdout=subprocess.DEVNULL)
    d = {}
    for t in ET.parse(sortie).getroot().findall("tripinfo"):
        d[t.get("id")] = (float(t.get("duration")), float(t.get("waitingTime")),
                          float(t.find("emissions").get("CO2_abs")) / 1000)
    return d

def moy(d, ids, i):
    return sum(d[v][i] for v in ids) / len(ids)

print(f"{'seed':<5}{'finis a/r':>10}{'axe n':>7}{'durée act.':>12}{'durée rés.':>12}"
      f"{'écart':>8}{'CO2 act.':>10}{'CO2 rés.':>10}")
ecarts = []
for s in SEEDS:
    a = lance("actuel", SCEN["actuel"], s)
    b = lance("reservee", SCEN["reservee"], s)
    communs = [v for v in ids_axe if v in a and v in b]
    da, db = moy(a, communs, 0), moy(b, communs, 0)
    ca, cb = moy(a, communs, 2), moy(b, communs, 2)
    ecarts.append(db - da)
    print(f"{s:<5}{str(len(a)) + '/' + str(len(b)):>10}{len(communs):>7}"
          f"{da:>12.1f}{db:>12.1f}{db - da:>+8.1f}{ca:>10.1f}{cb:>10.1f}")

print(f"\nécart moyen de durée (voitures de l'axe) : {statistics.mean(ecarts):+.1f} s")
print(f"écart-type : {statistics.stdev(ecarts):.1f} s")
print(f"tirages où la voie réservée est plus lente : {sum(1 for e in ecarts if e > 0)} sur {len(ecarts)}")