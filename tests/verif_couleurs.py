import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, "..", "data")

scenarios = ["actuel", "pic", "rue_fermee", "voie_reservee"]

for scenario in scenarios:
    filepath = os.path.join(data_dir, f"trafic_czml_{scenario}.json")
    
    if not os.path.exists(filepath):
        print(f"❌ Fichier introuvable : {filepath}")
        continue
        
    with open(filepath, "r") as f:
        data = json.load(f)
    
    # On cherche la couleur du premier véhicule (le 2ème élément du tableau, le 1er est le document)
    try:
        first_vehicle = data[1]
        color = first_vehicle["point"]["color"]["rgba"]
        path_color = first_vehicle["path"]["material"]["solidColor"]["color"]["rgba"]
        
        # On traduit le code RGB en nom de couleur pour t'aider
        nom_couleur = "Inconnue"
        if color[0] > 200 and color[1] < 100: nom_couleur = "ROUGE"
        if color[0] > 200 and color[1] > 100 and color[1] < 200: nom_couleur = "ORANGE"
        if color[0] < 100 and color[1] > 200: nom_couleur = "CYAN/BLEU"
        if color[0] < 150 and color[1] > 200 and color[2] < 150: nom_couleur = "VERT"

        print(f"✅ {scenario.ljust(15)} : Point {color} ({nom_couleur}) | Traînée {path_color}")
        
    except (IndexError, KeyError) as e:
        print(f"⚠️ {scenario} : Le fichier est vide ou mal formaté.")