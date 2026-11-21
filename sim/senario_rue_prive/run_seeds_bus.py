import os
import subprocess
import statistics
import xml.etree.ElementTree as ET

AXE = ["4330541#3", "4330541#7", "4330541#9", "4330541#10",
       "4330541#11", "4330541#12", "4330541#15", "4330541#18"]
SEEDS = range(1, 11)
FIN = 1500
SCEN = {"actuel": "../hassan.net.xml", "reservee": "hassan_voie_reservee_v3.net.xml"}

BUS = """<routes>
  <vType id="bus" vClass="bus" length="12" maxSpeed="16.67" accel="1.2" decel="3.5"/>
  <route id="axe" edges="{edges}"/>
  <flow id="bus" type="bus" route="axe" begin="{d}" end="1500" period="300" departLane="best" departSpeed="0"/>
</routes>"""

os.makedirs("runs", exist_ok=True)

ids_axe = set()
for _, el in ET.iterparse("../hassan.rou.xml", events=("end",)):
    if el.tag == "vehicle":
        r = el.find("route")
        if r is not None and r.get("edges") and any(e in AXE for e in r.get("edges").split()):
            ids_axe.add(el.get("id"))
        el.clear()

def lance(nom, net, seed):
    bus = f"runs/bus_{seed}.rou.xml"
    with open(bus, "w") as f:
        f.write(BUS.format(edges=" ".join(AXE), d=(seed - 1) * 9))
    sortie = f"runs/tripinfo_bus_{nom}_{seed}.xml"
    subprocess.run(["sumo", "-n", net, "-r", f"../hassan.rou.xml,{bus}", "-b", "0", "-e", str(FIN),
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

print(f"{'seed':<5}{'finis':>9}{'voit. axe: act.':>17}{'rés.':>7}{'écart':>8}"
      f"{'bus: act.':>11}{'rés.':>7}{'écart':>8}{'attente rés.':>14}")
ev, eb = [], []
for s in SEEDS:
    a = lance("actuel", SCEN["actuel"], s)
    b = lance("reservee", SCEN["reservee"], s)
    voit = [v for v in ids_axe if v in a and v in b]
    bus = [v for v in a if v.startswith("bus") and v in b]
    va, vb = moy(a, voit, 0), moy(b, voit, 0)
    ba, bb = moy(a, bus, 0), moy(b, bus, 0)
    ev.append(vb - va)
    eb.append(bb - ba)
    print(f"{s:<5}{str(len(a)) + '/' + str(len(b)):>9}{va:>17.1f}{vb:>7.1f}{vb - va:>+8.1f}"
          f"{ba:>11.1f}{bb:>7.1f}{bb - ba:>+8.1f}{moy(b, bus, 1):>14.1f}")

print(f"\nvoitures de l'axe : écart moyen {statistics.mean(ev):+.1f} s (écart-type {statistics.stdev(ev):.1f}),"
      f" plus lentes dans {sum(1 for e in ev if e > 0)} tirages sur {len(ev)}")
print(f"bus : écart moyen {statistics.mean(eb):+.1f} s (écart-type {statistics.stdev(eb):.1f}),"
      f" plus rapides dans {sum(1 for e in eb if e < 0)} tirages sur {len(eb)}")