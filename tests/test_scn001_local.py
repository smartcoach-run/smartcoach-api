# tests/test_scn001_local.py
"""
Test automatisé du scénario SCN_001 (Génération de plan)
Permet de valider la non-régression et le bon fonctionnement de l'API Flask.
"""

import requests
import json
from datetime import datetime

API_URL = "http://127.0.0.1:8000/generate_by_id"

# Liste d'IDs coureurs à tester (ex: récupérés d'Airtable)
COUREURS_TEST = [
    "recXXXXXXXX1",
    "recXXXXXXXX2",
    "recXXXXXXXX3"
]

def run_test(record_id: str):
    """Envoie une requête POST à l'API SmartCoach."""
    print(f"\n🚀 Test SCN_001 pour {record_id}")
    payload = {"record_id": record_id}
    r = requests.post(API_URL, json=payload)

    print(f"HTTP {r.status_code}")
    try:
        resp = r.json()
    except Exception:
        print("❌ Réponse non JSON")
        print(r.text)
        return

    if r.status_code == 200:
        print("✅ Succès :", resp.get("message"))
    else:
        print("⚠️ Erreur :", resp.get("message_id"), "-", resp.get("message"))

    # Enregistre le résultat
    with open(f"tests/logs/{record_id}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json", "w", encoding="utf-8") as f:
        json.dump(resp, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print("=== Tests SCN_001 (local) ===")
    for rid in COUREURS_TEST:
        run_test(rid)
    print("\n✅ Tous les tests exécutés.")
