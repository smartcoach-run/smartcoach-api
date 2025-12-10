# engine/war_room.py
# War Room MVP — évalue le niveau de risque pour la séance

def evaluate_war_room(profile, objectif, slot, historique, raw_session, mode: str) -> dict:
    """
    MVP : heuristiques très simples.

    On pourra brancher ici :
      - contraintes de charge
      - nombre de jours consécutifs
      - écarts par rapport au plan
      - état de forme (feedback)
    """

    duree = raw_session.get("duree_min") or raw_session.get("duree") or 0
    distance = raw_session.get("distance_km") or 0
    intensite = (raw_session.get("intensite") or "").upper()

    alerts = []
    level = "soft"

    # Exemple : durée très longue → medium
    if duree and duree > 90:
        level = "medium"
        alerts.append("Durée supérieure à 90 minutes (War Room MEDIUM).")

    # Exemple : distance très longue
    if distance and distance > 22:
        level = "medium"
        alerts.append("Distance > 22 km (War Room MEDIUM).")

    # Exemple : intensité élevée chez un niveau débutant
    niveau = profile.get("niveau") or profile.get("Niveau")
    if niveau == "Débutant" and intensite in ("T", "I", "R"):
        level = "medium"
        alerts.append("Intensité élevée pour un profil Débutant (War Room MEDIUM).")

    # TODO : utiliser historique pour monter à HARD / CRITICAL

    return {
        "level": level,
        "alerts": alerts,
        "notes": [],
    }
