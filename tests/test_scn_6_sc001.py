import json
from scenarios.agregateur.scn_6 import run_scn_6

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_scn_6_sc001_basic():
    input_json = load_json("tests/data/scn_6/sc001_input.json")
    
    result = run_scn_6(
        payload=input_json["payload"],
        record_id=input_json["record_id"]
    )

    assert result.success, f"Erreur retournée : {result.message}"

    # Contrôle minimal
    session = result.data["session"]
    assert session["duration_total"] == 54
    assert session["metadata"]["family"] == "MARA_REPRISE_Q1"
