"""
run_pipeline.py - M1 : zone OSM -> reseau SUMO -> simulation de test, en une commande.

Etapes :
  1. extract_zone.py   reseau et batiments (OSMnx)        -> network*.geojson, buildings.geojson, zone.json
  2. check_output.py   verification du livrable
  3. download_osm.py   routes au format .osm              -> hassan.osm
  4. netconvert        reseau SUMO                        -> hassan.net.xml
  5. randomTrips.py    trajets de test                    -> test.rou.xml
  6. sumo              simulation de 300 s                -> tripinfo.xml
  7. controle          au moins un vehicule arrive

Usage : python run_pipeline.py [--skip-extract] [--skip-download] [--end 300] [--period 2]
Le dossier de sortie est OUTPUT_DIR (Docker) ou <depot>/data. La zone vient de BBOX / ZONE_NAME.
"""
import argparse
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(os.getenv("OUTPUT_DIR") or HERE.parent / "data")
# Zone par defaut : Hassan (docs/zone.md), sauf si BBOX ou ZONE_NAME est defini
HASSAN_BBOX = "-6.838888737658811,34.01149086618757,-6.822631862341188,34.024965533812434"
if not os.getenv("BBOX") and not os.getenv("ZONE_NAME"):
    os.environ["BBOX"] = HASSAN_BBOX


def sumo_home():
    env = os.getenv("SUMO_HOME")
    if env and Path(env).exists():
        return Path(env)
    try:
        import sumo  # installe par pip (eclipse-sumo), cas du conteneur
        return Path(sumo.SUMO_HOME)
    except ImportError:
        sys.exit("SUMO introuvable : definissez SUMO_HOME ou installez eclipse-sumo.")


def tool(name):
    path = shutil.which(name)
    if not path:
        sys.exit(f"'{name}' introuvable dans le PATH. Installez SUMO et verifiez SUMO_HOME.")
    return path


def run(step, cmd):
    print(f"\n=== {step} ===")
    print("$", " ".join(str(c) for c in cmd), flush=True)
    result = subprocess.run([str(c) for c in cmd])
    if result.returncode != 0:
        sys.exit(f"ECHEC a l'etape : {step} (code {result.returncode})")


def count_trips(tripinfo):
    return sum(1 for _, el in ET.iterparse(tripinfo) if el.tag == "tripinfo")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-extract", action="store_true", help="ne pas refaire l'etape OSMnx (1 et 2)")
    ap.add_argument("--skip-download", action="store_true", help="reutiliser hassan.osm existant")
    ap.add_argument("--end", type=int, default=300, help="duree de la simulation (s)")
    ap.add_argument("--period", type=float, default=2, help="un vehicule toutes les N secondes")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    osm, net = OUT / "hassan.osm", OUT / "hassan.net.xml"
    trips, rou, tripinfo = OUT / "test.trips.xml", OUT / "test.rou.xml", OUT / "tripinfo.xml"

    if not args.skip_extract:
        run("1. Extraction OSMnx", [py, HERE / "extract_zone.py"])
        run("2. Verification", [py, HERE / "check_output.py"])
    if not args.skip_download:
        run("3. Telechargement .osm", [py, HERE / "download_osm.py"])
    if not osm.exists():
        sys.exit(f"{osm} introuvable.")

    run("4. Conversion SUMO", [
        tool("netconvert"), "--osm-files", osm, "-o", net,
        "--geometry.remove", "--roundabouts.guess", "--junctions.join", "--tls.guess-signals",
        "--remove-edges.isolated", "--keep-edges.by-vclass", "passenger", "--output.original-names"])

    run("5. Trajets de test", [
        py, sumo_home() / "tools" / "randomTrips.py", "-n", net, "-e", args.end, "-p", args.period,
        "-o", trips, "-r", rou, "--seed", 42, "--validate"])

    run("6. Simulation SUMO", [
        tool("sumo"), "-n", net, "-r", rou, "--tripinfo-output", tripinfo,
        "--end", args.end, "--no-step-log", "true"])

    n = count_trips(tripinfo)
    print(f"\n=== 7. Controle ===\n{n} vehicules arrives dans {tripinfo}")
    if n == 0:
        sys.exit("ERREUR : aucun vehicule n'est arrive.")
    print(f"OK : reseau {net.name} ({net.stat().st_size / 1e6:.1f} Mo), simulation de test reussie.")


if __name__ == "__main__":
    main()