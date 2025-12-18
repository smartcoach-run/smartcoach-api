import json
from pathlib import Path


def load_json(path: str) -> dict:
    """
    Chargement simple d'un fichier JSON (usage QA uniquement)
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"QA file not found: {path}")

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)
