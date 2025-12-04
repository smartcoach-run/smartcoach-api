from core.utils.logger import get_logger

log = get_logger("SCN_0e")

def run_scn_0e(slots: list, nb_semaines: int) -> list:
    """
    Retourne une liste de dict:
    [
        {"semaine": 1, "phase": "Prépa générale"},
        {"semaine": 2, "phase": "Prépa générale"},
        ...
    ]
    """

    try:
        phases = []

        # Exemple simple v2025 : 40% / 40% / 20%
        n1 = max(1, int(nb_semaines * 0.4))
        n2 = max(1, int(nb_semaines * 0.4))
        n3 = nb_semaines - n1 - n2

        phase_labels = (
            ["PHASE 1 — Base"]      * n1 +
            ["PHASE 2 — Développement"] * n2 +
            ["PHASE 3 — Affûtage"]  * n3
        )

        for i in range(nb_semaines):
            phases.append({
                "semaine": i + 1,
                "phase": phase_labels[i]
            })

        return phases

    except Exception as e:
        log.error(f"[SCN_0e] Erreur : {e}")
        raise e
