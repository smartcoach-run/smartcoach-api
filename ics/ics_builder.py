from datetime import datetime, timedelta
from uuid import uuid4


def build_ics(session: dict, start_hour: int = 7) -> str:
    """
    Génère un contenu ICS à partir d'une session SmartCoach
    """

    date_str = session["date"]  # YYYY-MM-DD
    duration = session["duration_total"]  # minutes
    family = session["metadata"].get("family", "SMARTCOACH_SESSION")
    session_id = session.get("session_id", str(uuid4()))

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

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//SmartCoach//EN
BEGIN:VEVENT
UID:{session_id}
DTSTAMP:{fmt(datetime.utcnow())}
DTSTART:{fmt(start_dt)}
DTEND:{fmt(end_dt)}
SUMMARY:SmartCoach – Séance {family}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR
"""

    return ics