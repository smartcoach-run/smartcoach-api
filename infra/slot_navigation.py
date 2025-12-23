from fastapi import APIRouter, Header, HTTPException
from datetime import date, timedelta
from pydantic import BaseModel, Field
from typing import Optional, Literal, Any, Dict
from core.utils.logger import get_logger
from services.airtable_tables import ATABLES
from services.airtable_service import AirtableService

# On réutilise le calcul de date du CORE_1 (utilitaire pur)
from infra.slot_resolution import compute_next_slot_date  # ajuste l'import si ton arborescence diffère

logger = get_logger("CORE_3")
ATABLES.SLOTS

router = APIRouter(prefix="/core", tags=["CORE_3"])

# -----------------------------
# Models
# -----------------------------
FeedbackStatus = Literal["OK", "PARTIAL", "NO"]

AdaptationMode = Literal["NEUTRAL", "HOLD", "DOWN"]

class Core3Input(BaseModel):
    runner_id: str = Field(..., description="Airtable record id (Coureurs)")
    previous_slot_id: str = Field(..., description="Airtable record id (Slots)")
    timezone: str = Field("Europe/Paris")
    dry_run: bool = False


class Core3Reasoning(BaseModel):
    feedback_used: bool
    feedback_status: Optional[str] = None
    adaptation_mode: AdaptationMode
    rule_applied: str


class Core3NextSlot(BaseModel):
    slot_id: str
    planned_date: str
    statut: str
    reasoning: Core3Reasoning


class Core3Output(BaseModel):
    ok: bool
    result: Dict[str, Any]


# -----------------------------
# Airtable adapter (placeholder)
# -----------------------------
class AirtableClient:
    """
    TODO: Remplace par TON client Airtable (celui que tu utilises déjà dans CORE_2).
    Objectif : centraliser get_record / create_record / update_record.
    """

    def get_record(self, table: str, record_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def find_records(self, table: str, formula: str) -> list[Dict[str, Any]]:
        raise NotImplementedError

    def create_record(self, table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def update_record(self, table: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


airtable = AirtableClient()

SLOTS_TABLE = "🧩 Slots"   # ajuste au nom exact
RUNNERS_TABLE = "👟 Coureurs"  # ajuste au nom exact


# -----------------------------
# Helpers
# -----------------------------
def normalize_feedback_status(raw: Any) -> str:
    return (raw or "").strip().upper()

def decide_adaptation(fb_status: str) -> tuple[AdaptationMode, str, str]:
    """
    v1 minimal : pas de feeling.
    """
    if fb_status == "NO":
        return "DOWN", "R1", "Feedback NO → DOWN"
    if fb_status == "PARTIAL":
        return "HOLD", "R2", "Feedback PARTIAL → HOLD"
    if fb_status == "OK":
        return "NEUTRAL", "R3", "Feedback OK → NEUTRAL"
    return "NEUTRAL", "R4", "No feedback → NEUTRAL"


def ensure_previous_slot_is_consumed(previous_slot_fields: Dict[str, Any]) -> None:
    """
    Aligné avec ta réalité actuelle : planned / pending / sent
    """
    statut = (previous_slot_fields.get("Statut") or "").strip().lower()
    if statut != "sent":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PREVIOUS_SLOT_NOT_CONSUMED",
                "expected": "sent",
                "actual": statut
            }
        )

def find_existing_next_slot(runner_id: str, previous_slot_id: str) -> Optional[Dict[str, Any]]:
    """
    Idempotence logique : si on a déjà créé un next slot pour ce previous_slot, on le renvoie.
    TODO: à adapter selon ton modèle (champ 'Previous_Slot_ID', lien, ou trace).
    """
    # Exemple : si tu stockes le previous_slot_id dans un champ texte 'Previous_Slot_ID'
    formula = f"AND({{Coureur_ID}}='{runner_id}', {{Previous_Slot_ID}}='{previous_slot_id}')"
    matches = airtable.find_records(SLOTS_TABLE, formula=formula)
    return matches[0] if matches else None


# -----------------------------
# Endpoint
# -----------------------------
@router.post("/next-slot", response_model=Core3Output)
def core_3_next_slot(
    payload: Core3Input,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """
    CORE_3 v1:
    - Vérifie previous_slot Statut == sent
    - Lit feedback_status (optionnel)
    - Décide adaptation_mode (NEUTRAL/HOLD/DOWN)
    - Calcule planned_date via CORE_1 (compute_next_slot_date)
    - Crée 1 slot suivant, trace la décision
    - Idempotent (logique) : renvoie le slot existant si déjà créé
    """
    logger.info(
        f"[CORE_3] runner_id={payload.runner_id} previous_slot_id={payload.previous_slot_id} "
        f"dry_run={payload.dry_run} idem_key={idempotency_key}"
    )

    # 1) Idempotence logique (optionnelle mais recommandée)
    try:
        existing = find_existing_next_slot(payload.runner_id, payload.previous_slot_id)
    except NotImplementedError:
        existing = None

    if existing:
        return {
            "ok": True,
            "result": {
                "status": "NEXT_SLOT_ALREADY_EXISTS",
                "runner_id": payload.runner_id,
                "previous_slot_id": payload.previous_slot_id,
                "next_slot_id": existing["id"],
            },
        }

    # 2) Charger previous slot
    prev = airtable.get_record(
        table_id=ATABLES.SLOTS,
        record_id=payload.previous_slot_id
    )

    if not prev:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SLOT_NOT_FOUND",
                "slot_id": payload.previous_slot_id
            }
        )

    prev_fields = prev.get("fields", {})


    # 3) Protection : doit être consommé (= sent)
    ensure_previous_slot_is_consumed(prev_fields)

    # 4) Lire feedback
    fb_status = normalize_feedback_status(prev_fields.get("feedback_status"))
    adaptation_mode, rule, decision_comment = decide_adaptation(fb_status)

    reasoning = {
        "feedback_used": bool(fb_status),
        "feedback_status": fb_status or None,
        "adaptation_mode": adaptation_mode,
        "rule_applied": rule,
    }

    # 5) Calcul date prochain slot (exemple minimal)
    # TODO: déterminer date_ref / day_index / days_allowed depuis ton contexte réel (runner + plan)
    # - date_ref : la date du slot précédent (champ date)
    # - day_index : weekday du slot précédent
    # - days_allowed : jours autorisés du coureur/plan
    date_ref = get_field(prev, ATFIELDS.DATE_SLOT)  # ajuste le nom du champ date du slot
    days_allowed = prev_fields.get("Days_allowed")  # idem
    day_index = prev_fields.get("Day_index")  # idem

    if not date_ref or days_allowed is None or day_index is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MISSING_SLOT_CONTEXT",
                "message": "Missing Date_slot / Days_allowed / Day_index on previous slot.",
                "details": {"Date_slot": date_ref, "Days_allowed": days_allowed, "Day_index": day_index},
            },
        )

    planned_date = (
        date.fromisoformat(date_ref) + timedelta(days=1)
    ).isoformat()

    # 6) Construire le nouveau slot (écriture Airtable)
    next_slot_fields = {
        "Coureur_ID": payload.runner_id,
        "_attach_previous_slot_id": payload.previous_slot_id,
        "Date_slot": planned_date,
        "Statut": "planned",
        "decision_source": "CORE_4",
        "decision_rule": rule,
        "decision_comment": decision_comment,
        "decision_json": reasoning,
    }

    if payload.dry_run:
        return {
            "ok": True,
            "result": {
                "runner_id": payload.runner_id,
                "previous_slot_id": payload.previous_slot_id,
                "next_slot": {
                    "slot_id": "DRY_RUN",
                    "planned_date": planned_date,
                    "statut": "planned",
                    "reasoning": reasoning,
                },
            },
        }

    else:
        created = airtable.upsert_record(
            table_id=ATABLES.SLOTS,
            key_field="_attach_previous_slot_id",
            key_value=payload.previous_slot_id,
            fields=next_slot_fields
        )

    return {
        "ok": True,
        "result": {
            "runner_id": payload.runner_id,
            "previous_slot_id": payload.previous_slot_id,
            "next_slot": {
                "slot_id": created["id"],
                "planned_date": planned_date,
                "statut": "planned",
                "reasoning": reasoning,
            },
        },
    }