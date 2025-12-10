# engine/bab_engine_mvp.py
# BAB Engine MVP — Running v1 (Option B + M3)

import logging
from datetime import datetime

from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error
from scenarios.socle.scn_0g import run_scn_0g  # SOCLE existant
from engine.war_room import evaluate_war_room  # à créer juste après

logger = logging.getLogger("BAB_ENGINE_MVP")


def run(run_context: dict) -> InternalResult:
    """
    Entrée unique du moteur BAB pour l'univers Running.

    run_context attendu :
    {
        "profile": {...},
        "objectif": {...},
        "slot": {...},
        "historique": [...],
        "mode": "ondemand" | "ics_j-1" | "ics_day" | "regen",
        "options": {...}
    }
    """

    try:
        profile = run_context.get("profile") or {}
        objectif = run_context.get("objectif") or {}
        slot = run_context.get("slot") or {}
        historique = run_context.get("historique") or []
        mode = run_context.get("mode", "ondemand")

        log_info(f"[BAB_ENGINE_MVP] run_context.mode={mode}")
        log_info(f"[BAB_ENGINE_MVP] slot={slot}")

        # -------------------------------------------------
        # 1) Déterminer un "type de séance" MVP
        #    (EF, Tempo, SL, Intensité, Repos, Fallback…)
        #    Ici on applique quelques heuristiques simples.
        # -------------------------------------------------
        seance_type = decide_session_type(profile, objectif, slot, historique, mode)
        log_info(f"[BAB_ENGINE_MVP] Type de séance choisi = {seance_type}")

        # -------------------------------------------------
        # 2) Construire les paramètres pour le SOCLE (SCN_0g)
        #    M3 = on guide SCN_0g avec un schéma de séance
        # -------------------------------------------------
        socle_payload = build_socle_payload(profile, objectif, slot, seance_type, historique,run_context)

        # ⚠️ IMPORTANT :
        # On suppose que run_scn_0g attend un contexte avec .payload
        # Si dans ton code réel la signature diffère, adapte juste cette partie.
        class DummyContext:
            def __init__(self, payload):
                self.payload = payload
                self.record_id = payload.get("record_id")

        socle_context = DummyContext(socle_payload)
        socle_result = run_scn_0g(socle_context)

        if socle_result.status == "error":
            log_error(f"[BAB_ENGINE_MVP] Erreur SOCLE SCN_0g : {socle_result.message}")
            return InternalResult.error(
                message=f"Erreur SOCLE SCN_0g : {socle_result.message}",
                source="BAB_ENGINE_MVP",
                data={"socle_error": socle_result.message}
            )

        raw = socle_result.data or {}

        # -------------------------------------------------
        # 3) War Room MVP
        # -------------------------------------------------
        war_room = evaluate_war_room(
            profile=profile,
            objectif=objectif,
            slot=slot,
            historique=historique,
            raw_session=raw,
            mode=mode,
        )

        # -------------------------------------------------
        # 4) Construire la session JSON standard SmartCoach
        # -------------------------------------------------
        session = build_session_json_standard(
            raw_socle_session=raw,
            profile=profile,
            objectif=objectif,
            slot=slot,
            mode=mode,
            war_room=war_room,
        )

        # Phase context MVP (pour l’instant très simple)
        phase_context = {
            "phase": slot.get("phase"),
            "seance_type": seance_type,
            "volume_target": session.get("distance_km"),
            "intensity_target": session.get("intensity_tags"),
        }

        return InternalResult.ok(
            message="[BAB_ENGINE_MVP] Séance générée",
            data={
                "session": session,
                "slot": slot,
                "war_room": war_room,
                "phase_context": phase_context,
            },
            source="BAB_ENGINE_MVP"
        )

    except Exception as e:
        log_error(f"[BAB_ENGINE_MVP] Exception inattendue : {e}")
        return InternalResult.error(
            message=f"Exception BAB_ENGINE_MVP : {e}",
            source="BAB_ENGINE_MVP",
            data={"exception": str(e)}
        )


# =====================================================================
#  Fonctions internes
# =====================================================================

def decide_session_type(profile, objectif, slot, historique, mode: str) -> str:
    """
    MVP : heuristiques très simples.
    À raffiner plus tard avec BF_x / SF_BLOC_xx.
    """
    niveau = profile.get("niveau") or profile.get("Niveau")
    phase = slot.get("phase") or slot.get("Phase")

    # Exemple très simple :
    # - si pas de profil → EF
    # - si phase spécifique → TEMPO ou ALLURE
    # - si plusieurs jours consécutifs → EF
    # - si long run déjà récent → EF ou récupération
    # etc.
    # Pour l'instant, on garde une logique MVP très prudente.

    if not niveau:
        return "EF"

    # Si on détecte une phase spécifique :
    if phase and "Spéc" in str(phase):
        return "TEMPO"

    # TODO: utiliser historique pour détecter fatigue / répétitions
    # Pour l'instant : EF par défaut
    return "EF"

def build_socle_payload(profile, objectif, slot, seance_type, historique, run_context):
    slot_id = slot.get("slot_id")
    record_id = (
        slot.get("record_id")
        or profile.get("record_id")
        or objectif.get("record_id")
        or run_context.get("record_id")      # 🔥 clé manquante
    )

    return {
        "profile": profile,
        "objectif": objectif,
        "slot": slot,

        # SOCLE KEYS
        "slot_id": slot_id,
        "record_id": record_id,

        "seance_type": seance_type,
        "historique": historique,
    }

def build_session_json_standard(raw_socle_session: dict,
                                profile: dict,
                                objectif: dict,
                                slot: dict,
                                mode: str,
                                war_room: dict) -> dict:
    """
    Transforme la sortie de SCN_0g en JSON standard SmartCoach.

    On suppose que SCN_0g renvoie au moins :
        - duree_min
        - distance_km
        - intensite
        - description
        - conseils
        - modele_cle
    """

    now_iso = datetime.utcnow().isoformat() + "Z"

    session_id = f"sess_{slot.get('date', 'unknown')}_{slot.get('slot_id', 'noid')}"
    user_id = profile.get("id") or profile.get("Coureur ID") or "unknown"

    duree = raw_socle_session.get("duree_min") or raw_socle_session.get("duree")
    distance_km = raw_socle_session.get("distance_km") or 0.0
    intensite = raw_socle_session.get("intensite") or "E"
    description = raw_socle_session.get("description") or "Séance générée par SmartCoach."
    conseils = raw_socle_session.get("conseils")
    modele_cle = raw_socle_session.get("modele_cle")

    # Pour le MVP, on ne construit pas encore les steps détaillés
    steps = raw_socle_session.get("steps") or []

    session = {
        "session_id": session_id,
        "slot_id": slot.get("slot_id"),
        "plan_id": objectif.get("plan_id") or objectif.get("Objectif ID"),
        "user_id": user_id,

        "title": modele_cle or f"Séance {intensite}",
        "description": description,
        "date": slot.get("date"),
        "phase": slot.get("phase"),
        "type": raw_socle_session.get("type", "Séance"),

        "duration_min": duree,
        "distance_km": distance_km,
        "load": raw_socle_session.get("charge"),
        "intensity_tags": [intensite] if intensite else [],

        "steps": steps,

        "war_room": war_room,

        "phase_context": {},  # rempli au-dessus dans BAB_ENGINE

        "metadata": {
            "generated_at": now_iso,
            "mode": mode,
            "engine_version": "1.0.0-mvp",
            "socle_version": "SCN_0g",
        }
    }

    # On renvoie session ; phase_context sera injecté à l'extérieur
    return session
