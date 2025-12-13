# scn_0h_exec.py
# SOCLE — SCN_0h_exec
# Persistence d'une exécution de séance (OnDemand)
# Version : v1
# ⚠️ Ne pas utiliser pour la persistance STRUCTURE (planning)

from datetime import datetime
from services.airtable_service import upsert_record, get_record_by_id

SCN_NAME = "SCN_0h_exec"


def run_scn_0h_exec(payload: dict) -> dict:
    """
    Persiste le résultat d'une génération de séance pour un slot donné.
    Opération idempotente.
    """

    try:
        # 1️⃣ Vérifications minimales
        slot_id = payload.get("slot_id")
        session = payload.get("session")
        timestamp = payload.get("timestamp")

        if not slot_id:
            return _error("slot_id manquant")

        if not session:
            return _error("session manquante")

        if not timestamp:
            # fallback contrôlé
            timestamp = datetime.utcnow().isoformat()

        # 2️⃣ Charger le slot existant
        record = get_record_by_id(table="Slots", record_id=slot_id)
        if not record:
            return _error(f"Slot introuvable : {slot_id}")

        fields = record.get("fields", {})

        # 3️⃣ Garde-fou idempotence
        if fields.get("Timestamp_generation"):
            return {
                "status": "ok",
                "message": f"{SCN_NAME} : slot déjà persisté",
                "data": {
                    "slot_id": slot_id,
                    "timestamp": fields.get("Timestamp_generation"),
                },
                "source": SCN_NAME,
            }

        # 4️⃣ Préparer les champs à écrire (STRICTEMENT LIMITÉS)
        update_fields = {
            "Session JSON": session,
            "Timestamp_generation": timestamp,
            "Statut": "generated",
            "seance_id": f"SEANCE_{slot_id}",
        }

        # 5️⃣ Upsert (update uniquement)
        upsert_record(
            table="Slots",
            record_id=slot_id,
            fields=update_fields,
        )

        # 6️⃣ Retour standardisé
        return {
            "status": "ok",
            "message": f"{SCN_NAME} : exécution enregistrée",
            "data": {
                "slot_id": slot_id,
                "timestamp": timestamp,
            },
            "source": SCN_NAME,
        }

    except Exception as e:
        return _error(str(e))


def _error(message: str) -> dict:
    return {
        "status": "error",
        "message": f"{SCN_NAME} : {message}",
        "source": SCN_NAME,
    }
