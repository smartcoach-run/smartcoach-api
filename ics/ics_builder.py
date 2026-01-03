# ICS stable – ne pas modifier sans test local + import agenda
# Le 13/12/2025
from core.internal_result import InternalResult
from core.utils.logger import log_error, log_info

from datetime import datetime, timedelta

from uuid import uuid4

from zoneinfo import ZoneInfo

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

def build_ics(
    session: dict,
    *,
    start_hour: int = 7,
    location: str | None = None,
) -> str:
    """
    Génère un contenu ICS à partir d'une session SmartCoach
    """

    date_str = session.get("date")
    if not date_str:
        raise ValueError("ICS: session.date manquante")

    # Patch Make: parfois date arrive sous forme '"2025-12-15"'
    date_str = str(date_str).strip().strip('"')
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
    session_id = (
        session.get("session_id")
        or session.get("slot_id")
        or uuid4().hex
    )

    uid = f"{session_id}@smartcoach.run"

    tz = ZoneInfo("Europe/Paris")
    # Début / fin
    start_dt = datetime.strptime(
        f"{date_str} {start_hour:02d}:00",
        "%Y-%m-%d %H:%M"
    ).replace(tzinfo=tz)

    end_dt = start_dt + timedelta(minutes=duration)

    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%S")

    # Description lisible
    lines = []

    duration = session.get("duration_min")
    distance = session.get("distance_km")
    phase = session.get("phase")
    intensity_tags = session.get("intensity_tags", [])

    lines = []

    # En-tête SmartCoach
    lines.append(f"🏃 SmartCoach – {session.get('title', 'Séance')}")
    if phase:
        lines.append(f"Phase : {phase}")
    lines.append(f"Durée : {duration} min")

    if distance:
        lines.append(f"Distance : {distance} km")

    if intensity_tags:
        lines.append(f"Intensité : {', '.join(intensity_tags)}")

    lines.append("")
    lines.append("📋 Déroulé de la séance")

    blocks = (
        session
        .get("session_spec", {})
        .get("blocks", [])
    )
    if not blocks:
        for idx, step in enumerate(session.get("steps", []), start=1):
            label = step.get("label", "Bloc")
            d = step.get("duration_min", "?")
            comment = step.get("comment")

            line = f"{idx}) {label} ({d} min)"
            if comment:
                line += f" – {comment}"

            lines.append(line)

    for idx, block in enumerate(blocks, start=1):
        desc = block.get("description", "Bloc")
        d = block.get("duration_min", "?")
        intensity = block.get("intensity", {}).get("value")

        line = f"{idx}) {desc} ({d} min)"
        if intensity:
            line += f" [{intensity}]"

        lines.append(line)

    # Messages coach
    coach_notes = (
        session
        .get("session_spec", {})
        .get("coach_notes", [])
    )

    if coach_notes:
        lines.append("")
        lines.append("💡 Conseils du coach")
        for note in coach_notes:
            lines.append(f"• {note}")

    description = "\\n".join(lines)

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//SmartCoach//EN
BEGIN:VEVENT
UID:{uid}
SEQUENCE:0
DTSTAMP:{fmt(datetime.utcnow())}
DTSTART;TZID=Europe/Paris:{fmt(start_dt)}
DTEND;TZID=Europe/Paris:{fmt(end_dt)}
SUMMARY:SmartCoach – {session.get("title", "Séance")}
DESCRIPTION:{description}
"""

    if location:
        ics += f"\nLOCATION:{location}"

    ics += """

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