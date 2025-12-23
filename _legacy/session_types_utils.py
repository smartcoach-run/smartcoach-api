# =====================================================================
# utils/session_types_utils.py  (Version SmartCoach 2025 — STABLE)
# =====================================================================

from services.airtable_fields import ST
from models.session_type import SessionType
import logging

logger = logging.getLogger("SessionTypesUtils")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _g(fields: dict, key: str):
    """Récupère un champ Airtable proprement."""
    if not key or key not in fields:
        return None
    return fields.get(key)


def _list(raw):
    """Convertit un champ Airtable potentiellement liste en vraie liste."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    return [raw]


# ---------------------------------------------------------------------
# Validation légère
# ---------------------------------------------------------------------

def validate_session_type(sess: SessionType):
    """Vérifie les champs critiques d’une séance type."""
    if not sess.nom:
        logger.warning(f"[{sess.id}] ⚠️ Pas de nom → modèle inutilisable.")

    if not sess.cle_seance:
        logger.warning(f"[{sess.id}] ⚠️ Pas de clé_séance → tri impossible.")

    if sess.duree is None and sess.distance is None:
        logger.warning(f"[{sess.id}] ⚠️ Ni durée ni distance → modèle incomplet.")

    return sess


# ---------------------------------------------------------------------
# Mapping Airtable → SessionType (CORE SMARTCOACH)
# ---------------------------------------------------------------------

def map_record_to_session_type(record):
    """Construit un modèle SessionType à partir d’un record Airtable."""

    fields = record.get("fields", {})
    sess = SessionType()

    # -----------------------------
    # Identification générale
    # -----------------------------
    sess.id = record.get("id")
    sess.nom = _g(fields, ST.NOM)
    sess.cle_seance = _g(fields, ST.CLE_SEANCE)

    # -----------------------------
    # Classification
    # -----------------------------
    sess.mode = _list(_g(fields, ST.MODE))              # Running / Vitalité / Kids / Hyrox
    sess.phase_ids = _list(_g(fields, ST.PHASE_CIBLE))  # Phase 1 / Base / Prog...
    sess.categorie = _g(fields, ST.CATEGORIE)           # Endurance / VMA / Seuil…
    sess.cle_technique = _g(fields, ST.CLE_TECHNIQUE)   # Affutage-Seuil-T

    # 🔑 Clé interne SmartCoach (EF, EA, AS10, ACT, OFF...)
    sess.cat_smartcoach = _g(fields, ST.CAT_SMARTCOACH)

    # -----------------------------
    # Paramètres athlète
    # -----------------------------
    sess.niveau = _g(fields, ST.NIVEAU)

    # -----------------------------
    # Durées & intensité
    # -----------------------------
    sess.duree = _g(fields, ST.DUREE)
    sess.duree_moy = _g(fields, ST.DUREE_MOY)
    sess.repetitions = _g(fields, ST.REPETITIONS)
    sess.recup = _g(fields, ST.RECUP)

    # IMPORTANT :
    # Distance n’existe pas dans Airtable → on normalise en None
    sess.distance = None

    # -----------------------------
    # Allures & VDOT
    # -----------------------------
    sess.allure_cible = _g(fields, ST.ALLURE_CIBLE)
    sess.vdot = _g(fields, ST.VDOT)

    # Champs Kids / Vitalité / Hyrox
    sess.kids_duree = _g(fields, ST.KIDS_DUREE)
    sess.vitalite_duree = _g(fields, ST.VITALITE_DUREE)
    sess.hyrox_station = _g(fields, ST.HYROX_STATION)

    # -----------------------------
    # Description & conseils
    # -----------------------------
    sess.description = _g(fields, ST.DESCRIPTION)
    sess.conseil_coach = _g(fields, ST.CONSEIL_COACH)

    # -----------------------------
    # Champs nécessaires SCN_3 et SCN_6
    # -----------------------------
    # SCN_3 : filtrage univers / phase
    sess.univers = _list(_g(fields, ST.MODE))

    # SCN_6 : type_allure = clé SmartCoach
    sess.type_allure = sess.cat_smartcoach

    # Objectifs : pas dans Airtable Séances Types
    sess.objectifs = []

    # -----------------------------
    # Validation
    # -----------------------------
    return validate_session_type(sess)
