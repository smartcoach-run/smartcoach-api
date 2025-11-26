import pytest

from smartcoach_api.scenarios.scn_1 import (
    build_step4_running,
    apply_phases_and_progression
)

# Ordre canonique attendu pour tous les tests
ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
ORDER_MAP = {d: i for i, d in enumerate(ORDER)}


def test_step4_step5_preserve_order():
    """
    Vérifie que Step4 corrige correctement l'ordre des jours
    et que Step5 (ajout des phases + progression) préserve cet ordre.
    
    Ce test DOIT échouer automatiquement si un futur patch
    casse l'ordre canonique dans Step4 ou Step5.
    """

    # ────────────────────────────────────────────────
    # 1. Jeu de données volontairement désordonné
    # ────────────────────────────────────────────────
    jours_user = ["Dimanche", "Mardi"]
    jours_props = ["Vendredi"]

    # Attendu canonique (tri naturel)
    expected = ["Mardi", "Vendredi", "Dimanche"]

    # Construire Step4 (fonction réelle du moteur)
    step4 = build_step4_running(
        distance="10K",
        nb_semaines=3,
        jours_retenus_raw=jours_user + jours_props
    )

    # ────────────────────────────────────────────────
    # 2. Vérification Step4
    # ────────────────────────────────────────────────
    assert step4["jours_retenus"] == expected, (
        f"Step4 n'a PAS conservé l'ordre canonique.\n"
        f"Attendu : {expected}\n"
        f"Obtenu  : {step4['jours_retenus']}"
    )

    # Les slots de chaque semaine doivent être triés
    for i, week in enumerate(step4["weeks"]):
        got = [slot["jour"] for slot in week["slots"]]
        assert got == expected, (
            f"Step4 → semaine {i+1} : slots mal triés.\n"
            f"Attendu : {expected}\n"
            f"Obtenu  : {got}"
        )

    # ────────────────────────────────────────────────
    # 3. Vérification Step5
    # ────────────────────────────────────────────────
    # Phases simplifiées pour le test
    phases_fake = [
        {"phase": "Build", "charge": 1.0},
        {"phase": "Affûtage", "charge": 0.75},
        {"phase": "Course", "charge": 0.25},
    ]

    weeks5 = apply_phases_and_progression(step4["weeks"], phases_fake)

    for i, week in enumerate(weeks5):
        got = [slot["jour"] for slot in week["slots"]]
        assert got == expected, (
            f"Step5 → semaine {i+1} : slots mal triés après progression.\n"
            f"Attendu : {expected}\n"
            f"Obtenu  : {got}"
        )
