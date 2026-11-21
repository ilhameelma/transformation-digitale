<#
  Scenario 3 : pic de trafic +30 %
  A lancer depuis la RACINE du depot (dossier qui contient docker-compose.yml) :
      .\scenario_pic.ps1            premiere fois
      .\scenario_pic.ps1 -Force     pour refaire le scenario (ecrase les anciens resultats 'pic')

  Hypothese : les services docker compose s'appellent "traffic" (Dockerfile.traffic) et "m1" (Dockerfile.m1).
  Sinon, remplacez les noms ci-dessous.
#>
param([switch]$Force)

function Step($titre, [scriptblock]$cmd) {
    Write-Host "`n=== $titre ===" -ForegroundColor Cyan
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "Echec a l'etape : $titre" }
}

$extra = @()
if ($Force) { $extra = @("--force") }

Step "1/5 Construction des conteneurs (scripts mis a jour)" { docker compose build traffic m1 }
Step "2/5 Demande +30 % : 500 x 1,3 = 650 vehicules" { docker compose run --rm traffic python generate_demand.py --scale 1.3 --out /data/demand_pic.csv }
Step "3/5 Simulation SUMO du scenario pic" { docker compose run --rm m1 python run_scenario.py --scenario pic @extra }
Step "4/5 Calcul des indicateurs" { docker compose run --rm traffic python compute_kpi.py --scenario pic }
Step "5/5 Fichier CZML pour la vue Cesium" { python tests/convert_to_czml.py --scenario pic }

Write-Host "`nTermine. Fichiers crees dans data/ : demand_pic.csv, trajectories_pic.json, kpi_pic.json, run_pic.json" -ForegroundColor Green
Write-Host "Reconstruisez l'application pour voir le selecteur : docker compose up -d --build react-viz"
