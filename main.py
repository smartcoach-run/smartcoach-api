import json
from qualite import controle_rg  # Assure-toi que le fichier est dans un dossier `qualite/controle_rg.py`

def main():
    # Simule la récupération des données depuis Postman ou Make (pour test local)
    with open("input.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    fields = data.get("fields", {})

    # 🔍 Étape 1 : Appliquer les règles qualité
    fields = controle_rg.run_regles(fields)

    # 🔁 Étape 2 : Traitement principal (placeholder ici)
    print("=== FIELDS MIS À JOUR ===")
    for k, v in fields.items():
        print(f"{k}: {v}")

    # (Éventuellement : renvoyer un résultat JSON ou l’écrire dans un fichier)
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump({"fields": fields}, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
