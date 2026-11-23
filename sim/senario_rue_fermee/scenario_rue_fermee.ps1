<#
  Scenario : rue fermee (Avenue Allal Ben Abdellah), meme methode que senario_rue_prive (voie reservee) :
  demande de reference sim/hassan.rou.xml jamais modifiee, 10 tirages, comparaison des voitures de la rue.

  A lancer depuis la RACINE du depot (dossier qui contient docker-compose.yml) :
      .\scenario_rue_fermee.ps1            premiere fois
      .\scenario_rue_fermee.ps1 -Force     refaire (ecrase les fichiers deja publies dans data/)

  Les scripts de sim/senario_rue_fermee tournent dans le conteneur "traffic" (il contient SUMO),
  avec le dossier sim/ monte : rien a installer sur le PC.
#>
param([switch]$Force)

function Step($titre, [scriptblock]$cmd) {
    Write-Host "`n=== $titre ===" -ForegroundColor Cyan
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "Echec a l'etape : $titre" }
}
function Sim($script, $arguments) {
    docker compose run --rm -v "${PWD}/sim:/sim" -w /sim/senario_rue_fermee traffic python $script @arguments
}
function Kpi($nom) {
    docker compose run --rm traffic python compute_kpi.py --scenario $nom
}

$extra = @()
if ($Force) { $extra = @("--force") }

Step "1/9 Construction du conteneur traffic"                  { docker compose build traffic }
Step "2/9 Reseau avec la rue fermee"                          { Sim "make_rue_fermee.py" @() }
Step "3/9 Demande : seules les voitures de la rue sont deviees" { Sim "make_demande_fermee.py" @() }
Step "4/9 10 tirages (20 simulations)"                        { Sim "run_seeds.py" @() }
Step "5/9 Tirage 1 detaille (animation et indicateurs)"       { Sim "run_demo.py" @() }
Step "6/9 Indicateur de la rue"                               { Sim "kpi_axe.py" @() }
Step "7/9 Publication dans data/"                             { Sim "publier.py" $extra }
Step "8/9 Indicateurs : situation actuelle"                   { Kpi "actuel_ref" }
Step "9/9 Indicateurs : rue fermee"                           { Kpi "rue_fermee" }

Write-Host "`nTermine. Reconstruisez l'application : docker compose up -d --build react-viz" -ForegroundColor Green
Write-Host "Puis ouvrez http://localhost:5173/rue-fermee"
