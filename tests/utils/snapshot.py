import json

def assert_snapshot(actual, expected_file):
    with open(expected_file, "r", encoding="utf-8") as f:
        expected = json.load(f)

    assert actual == expected, "Le snapshot ne correspond plus (régression détectée)"
