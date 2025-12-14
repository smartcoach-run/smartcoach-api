import json
from scenarios.agregateur.scn_6 import run_scn_6
from tests.utils.snapshot import assert_snapshot

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_scn_6_sc002_snapshot():
    input_json = load_json("tests/data/scn_6/sc002_input.json")

    result = run_scn_6(
        payload=input_json["payload"],
        record_id=input_json["record_id"]
    )

    assert result.success, f"Erreur retournée : {result.message}"

    assert_snapshot(
        actual=result.data,
        expected_file="tests/data/scn_6/sc002_expected.json"
    )
