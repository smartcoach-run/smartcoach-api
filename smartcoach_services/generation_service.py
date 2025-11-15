# smartcoach_services/generation_service.py

"""
generation_service.py
---------------------

Version V1 (squelette) : pas de logique métier, seulement la structure.

Rôle :
- Définir les points d'entrée pour la génération du plan et des séances.
- Construire des objets de retour standardisés (ok / plan / sessions / logs).
- Ne PAS accéder directement à Airtable.
- Ne PAS recalculer les dates ou les phases (tout viendra de ctx plus tard).

Ce module est volontairement "neutre" pour éviter toute régression
tant que les règles complètes de génération ne sont pas stabilisées.
"""

from typing import Dict, Any, List
from smartcoach_core.config import SMARTCOACH_DEBUG


# --------------------------------------------------------------------
# Utils internes
# --------------------------------------------------------------------

def _log(msg: str, logs: List[str]) -> None:
    """Ajoute un message aux logs et l'affiche en debug."""
    logs.append(msg)
    if SMARTCOACH_DEBUG:
        print(f"[GENERATION] {msg}")


def _error(message: str, logs: List[str]) -> Dict[str, Any]:
    """Retour d'erreur standardisé pour ce module."""
    _log(f"ERREUR: {message}", logs)
    return {
        "ok": False,
        "error": message,
        "logs": logs,
    }


# --------------------------------------------------------------------
# Point d'entrée 1 : génération du plan
# --------------------------------------------------------------------

def generate_plan(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Génère la structure du plan à partir du contexte.

    V1 (squelette) :
    - Ne calcule rien.
    - Utilise uniquement les valeurs déjà présentes dans ctx.
    - Vérifie la présence des éléments indispensables.
    - Construit un objet 'plan' minimal mais cohérent.

    ctx doit contenir au minimum :
        - date_debut_plan
        - date_objectif
        - jours_dispo (ou nb_jours_final)
    """

    logs: List[str] = []
    _log("Début generate_plan (V1)", logs)

    date_debut = ctx.get("date_debut_plan")
    date_objectif = ctx.get("date_objectif")
    jours_dispo = ctx.get("jours_dispo") or []
    nb_jours_final = ctx.get("nb_jours_final", len(jours_dispo))

    # Contrôles minimums (sans logique métier)
    if not date_debut:
        return _error("date_debut_plan absente du contexte.", logs)

    if not date_objectif:
        return _error("date_objectif absente du contexte.", logs)

    # Dans V1, on ne calcule pas le nombre de semaines.
    # On se contente de poser un champ éventuellement None.
    nb_semaines = ctx.get("nb_semaines_plan")

    plan = {
        "date_debut": date_debut,
        "date_objectif": date_objectif,
        "nb_semaines": nb_semaines,
        "nb_seances_semaine": nb_jours_final,
        # Espace réservé pour les futures phases (V2/V3)
        "phases": ctx.get("phases_plan", []),
        # Espace réservé pour méta-infos
        "meta": {
            "mode": ctx.get("mode"),
            "niveau": ctx.get("niveau"),
            "objectif": ctx.get("objectif"),
        },
    }

    _log("Plan généré (structure V1, sans logique métier).", logs)

    return {
        "ok": True,
        "plan": plan,
        "logs": logs,
    }


# --------------------------------------------------------------------
# Point d'entrée 2 : génération des séances
# --------------------------------------------------------------------

def generate_sessions(ctx: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Génère la liste des séances à partir d'un plan.

    V1 (squelette) :
    - Ne génère aucune vraie séance.
    - Retourne simplement une liste vide et des logs.
    - La structure est prête pour être enrichie en V2/V3.

    Arguments :
        ctx  : contexte complet SCN_1 (jours_dispo, mode, niveau, etc.)
        plan : dictionnaire retourné par generate_plan()
    """

    logs: List[str] = []
    _log("Début generate_sessions (V1)", logs)

    if not plan or not plan.get("date_debut"):
        return _error("Plan invalide ou incomplet (date_debut manquante).", logs)

    # V1 : aucune génération réelle, on prépare juste la structure.
    sessions: List[Dict[str, Any]] = []

    _log("Aucune séance générée (V1 - squelette seulement).", logs)

    return {
        "ok": True,
        "sessions": sessions,
        "logs": logs,
    }