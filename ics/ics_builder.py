# ICS stable – ne pas modifier sans test local + import agenda
# Le 13/12/2025
from datetime import datetime, timedelta
from uuid import uuid4
from core.internal_result import InternalResult
from core.utils.logger import log_error, log_info

MODULE_NAME = "ICS"

def run_generate_ics(context) -> InternalResult:
    try:
        payload = getattr(context, "payload", {}) or {}
        session = payload.get("session")

        if not session:
            raise ValueError("ICS: session manquante dans le payload")

        ics_content = build_ics(session)

        log_info("[ICS] Fichier ICS généré", module=MODULE_NAME)

        return InternalResult.ok(
            message="ICS généré",
            source=MODULE_NAME,
            data={
                "ics": ics_content
            }
        )

    except Exception as e:
        log_error(f"[ICS] Exception : {e}", module=MODULE_NAME)
        return InternalResult.error(
            message=f"Exception ICS : {e}",
            source=MODULE_NAME,
            data={}
        )
def build_ics(session: dict, start_hour: int = 7) -> str:
    """
    Génère un contenu ICS à partir d'une session SmartCoach
    """

    date_str = session.get("date")
    if not date_str:
        raise ValueError("ICS: session.date manquante")

    # Patch Make: parfois date arrive sous forme '"2025-12-15"'
    date_str = str(date_str).strip().strip('"')

    start_dt = datetime.strptime(
        f"{date_str} {start_hour:02d}:00",
        "%Y-%m-%d %H:%M"
    )

    duration = session.get("duration_min")

    if duration is None:
        # fallback intelligent
        steps = session.get("steps", [])
        if steps:
            duration = sum(
                int(step.get("duration_min", 0))
                for step in steps
                if step.get("duration_min") is not None
            )

    if not duration:
        raise ValueError("ICS: durée introuvable (session.duration_min ou steps.duration_min)")

    title = session.get("title", "Séance SmartCoach")
    session_id = session["session_id"]   # celui-ci existe toujours

    # Début / fin
    start_dt = datetime.strptime(f"{date_str} {start_hour:02d}:00", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration)

    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%S")

    # Description lisible
    steps_desc = []
    for step in session.get("steps", []):
        if step["type"] == "EF":
            steps_desc.append(f"- EF {step['duration_min']} min")
        elif step["type"] == "BLOCK":
            steps_desc.append(f"- Bloc x{step['repeats']}")
        elif step["type"] == "COOLDOWN":
            steps_desc.append(f"- Retour au calme {step['duration_min']} min")

    description = "\\n".join(steps_desc)
    uid = f"{session_id}@smartcoach.run"

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//SmartCoach//EN
BEGIN:VEVENT
UID:{uid}
SEQUENCE:0
DTSTAMP:{fmt(datetime.utcnow())}
DTSTART:{fmt(start_dt)}
DTEND:{fmt(end_dt)}
SUMMARY:SmartCoach – {session.get("title", "Séance")}
DESCRIPTION:{description}

BEGIN:VALARM
TRIGGER:-PT30M
ACTION:DISPLAY
DESCRIPTION:Rappel SmartCoach – séance dans 30 minutes
END:VALARM

BEGIN:VALARM
TRIGGER:-P1DT20H
ACTION:DISPLAY
DESCRIPTION:Rappel SmartCoach – séance demain
END:VALARM

END:VEVENT
END:VCALENDAR
"""


    return ics