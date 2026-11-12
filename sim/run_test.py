import subprocess

subprocess.run([
    "sumo", "-c", "rabat.sumocfg",
    "--additional-files", "additional.xml",
    "--tripinfo-output", "/data/tripinfo.xml",
    "--fcd-output", "/data/fcd.xml",
    "--fcd-output.geo", "true",
    "--device.emissions.probability", "1",
], check=True)
print("Simulation terminée, sorties dans /data")