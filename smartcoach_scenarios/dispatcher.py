"""
dispatcher.py
---------------------------------------------------------------------
Responsabilité :
Choisir quel scénario exécuter en fonction des données du contexte.

Ici, pour SmartCoach MVP :
- Uniquement SCN_1
- Architecture pensée pour être extensible (SCN_2, SCN_3… plus tard)

Conforme :
- RCTC (aucun champ ajouté)
- Story (1 scénario : génération plan)
- Manuel SmartCoach
---------------------------------------------------------------------
"""

from smartcoach_scenarios.scn_1 import scenario_1


def dispatch_scenario(ctx):
    """
    Router central :
    - ctx contient le record_id, les fields, l’instance Airtable, etc.
    - Le scénario à exécuter est déterminé ici.
    - Pour l’instant : uniquement SCN_1 (le scénario de génération)
    """

    try:
        # Debug mode affiché si demandé
        if ctx.get("debug"):
            print("[DISPATCHER] Contexte reçu :", ctx.keys())

        # ----------------------------------------------------------
        # Sélection du scénario
        # ----------------------------------------------------------
        # Aujourd’hui : aucun choix → toujours SCN_1
        # (sera extensible facilement si plusieurs scénarios arrivent)
        scenario_fn = scenario_1

        # ----------------------------------------------------------
        # Exécution
        # ----------------------------------------------------------
        result = scenario_fn(ctx)

        # Le résultat doit toujours être un dictionnaire
        if not isinstance(result, dict):
            return {
                "error": "Le scénario n’a pas retourné de dictionnaire.",
                "scenario": "SCN_1"
            }

        return result

    except Exception as e:
        print("[CRITICAL] Erreur dans dispatcher :", e)
        return {
            "error": "Erreur critique dans le dispatcher",
            "details": str(e)
        }