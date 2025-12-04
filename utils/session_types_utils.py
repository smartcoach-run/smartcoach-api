from typing import Dict, Any, List

# --------------------------------------------------
# Mapping interne SmartCoach → Airtable
# --------------------------------------------------
TYPE_MAP = {
    "E": "EF",
    "I": "I",
    "AS10": "AS10",
    "AS21": "AS21",
    "AS42": "AS42",
    "SL": "SL",
    "TECH": "TECH",
    "SEU": "SEU",
    "VMA": "VMA",
    "R": "R",
}

def ensure_list(value) -> List:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and "," in value:
        return [v.strip() for v in value.split(",")]
    return [value]


def map_record_to_session_type(record: Dict[str, Any]) -> Dict[str, Any]:
    fields = record.get("fields", record)

    session_id = fields.get("Clé séance") or fields.get("ID") or record.get("id")
    nom = fields.get("Nom de la séance type") or fields.get("Nom") or "Séance"
    univers = fields.get("Mode") or "Running"

    phase_ids = ensure_list(fields.get("Phase cible"))
    slot_types = ensure_list(fields.get("Type séance (court)"))
    niveaux = ensure_list(fields.get("Niveau"))

    duree = fields.get("Durée") or fields.get("Durée séance") or None
    if isinstance(duree, str) and duree.isdigit():
        duree = int(duree)

    distance = fields.get("Distance", None)
    objectifs = ensure_list(fields.get("Objectif"))

    tags = []
    for col in [
        "Catégorie",
        "Environnement conseillé",
        "Matériel requis",
        "Objectifs compatibles",
    ]:
        if fields.get(col):
            tags.extend(ensure_list(fields[col]))

    # --------------------------------------------------
    # MAPPING DU TYPE → adaptation des clés SCN_3 → Airtable
    # --------------------------------------------------
    slot_types_mapped = [TYPE_MAP.get(t, t) for t in slot_types]

    return {
        "session_type_id": session_id,
        "nom": nom,
        "univers": univers,
        "phase_ids": phase_ids,
        "slot_types": slot_types_mapped,
        "niveaux": niveaux,
        "duree": duree,
        "distance": distance,
        "objectifs": objectifs,
        "tags": tags,
        "raw": record,
    }
