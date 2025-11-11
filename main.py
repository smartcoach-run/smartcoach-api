# -*- coding: utf-8 -*-
"""
SmartCoach API — main_v2.py
Version: 2025-11-10 (SCN_01 compliant)

Conformité SCN_01 (pipeline d'orchestration) :
1) Charger coureur
2) Contrôle des jours disponibles (B03-COH-03/04/05/06) → SC_COACH_021..024
3) Vérifier quota (RG-GEST-QUOTA) → SC_COACH_031
4) Calcul durée plan (RG-DUREE-PLAN-01) depuis date_debut_plan/date_fin_plan si fournis, sinon fallback
5) Archivage versionné (RG-ARCH-01) : move → "Archives Séances" puis purge table "Séances"
6) Grille S×J déterministe (offsets figés)
7) Sélection séances types (RG-SELECT-SEANCE) + fallback (niveau -1) → SC_COACH_061
8) Insertion des séances + rollback si échec partiel → SC_COACH_071

Décisions figées :
- Durée du plan gelée après calcul
- Version précédente jamais écrasée (archivage) ; incrément version seulement si création effective
- Dernière semaine = Phase "Course" avec VEILLE (J-1) et RACE (Jour J)
"""

import os
import json
import traceback
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, date

from flask import Flask, request, jsonify
from pyairtable import Api
from airtable import airtable_get_all, airtable_get_one
from reference_jours import lookup_reference_jours

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

AIRTABLE_KEY = os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID") or os.environ.get("BASE_ID")

if not AIRTABLE_KEY or not BASE_ID:
    raise RuntimeError("AIRTABLE_API_KEY / AIRTABLE_BASE_ID manquants.")

api = Api(AIRTABLE_KEY)

# Noms des tables (adapter aux noms exacts de ta base)
T_COUR = "👤 Coureurs"
T_SEANCES = "🏋️ Séances"
T_TYPES = "📘 Séances types"
T_PARAM = "⚙️ Paramètres phases"
T_MSGS = "🗂️ Messages SmartCoach"      # optionnel
T_LOGS = "🧱 Logs SmartCoach"          # optionnel
T_GROUPES = "👥 Groupes"               # optionnel
T_ARCHIVES = "Archives Séances"        # table d'archives (mouvement)
T_REF_JOURS = "⚖️ Référence Jours"   
T_SUIVI = "📋 Suivi génération"

# Ouverture tables
TAB_COUR    = api.table(BASE_ID, T_COUR)
TAB_SEANCES = api.table(BASE_ID, T_SEANCES)
TAB_TYPES   = api.table(BASE_ID, T_TYPES)
TAB_PARAM   = api.table(BASE_ID, T_PARAM)
TAB_REF_JOURS = api.table(BASE_ID, T_REF_JOURS)
TAB_SUIVI = api.table(BASE_ID, T_SUIVI)

try:
    TAB_MSGS = api.table(BASE_ID, T_MSGS)
except Exception:
    TAB_MSGS = None

try:
    TAB_LOGS = api.table(BASE_ID, T_LOGS)
except Exception:
    TAB_LOGS = None

try:
    TAB_GROUPES = api.table(BASE_ID, T_GROUPES)
except Exception:
    TAB_GROUPES = None

try:
    TAB_ARCHIVES_T = api.table(BASE_ID, T_ARCHIVES)
except Exception:
    TAB_ARCHIVES_T = None

# Paramètres par défaut
DEFAULT_WEEKS = 10
DEFAULT_JOURS_SEMAINE = 2
DEFAULT_MODE = "Running"
MESSAGE_ID_QUOTA = "SC_COACH_031"

# Tolérance noms de champs
F_DATE_COURSE = ["date_course", "Date course", "Date objectif", "Jour de course", "Date Objectif"]
F_OBJECTIF = ["Objectif", "Objectif (normalisé)", "Objectif_normalisé", "Type objectif normalisé"]
F_NIVEAU = ["Niveau", "Niveau (normalisé)", "Niveau_normalisé", "Niveau coach"]
F_MODE = ["Mode", "Mode (normalisé)"]
F_JOURS_LIST = ["Jours disponibles", "jours_disponibles", "Disponibilités"]
F_JOURS_MIN = ["Nb_jours_min", "Nb_jours_min (calc)", "Jours_min"]
F_JOURS_MAX = ["Nb_jours_max", "Nb_jours_max (calc)", "Jours_max"]

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

def fget(fields: Dict[str, Any], names: List[str], default=None):
    for n in names:
        if n in fields and fields[n] not in (None, ""):
            return fields[n]
    return default


def to_int(v, default=0) -> int:
    try:
        if v in (None, ""):
            return default
        return int(float(v))
    except Exception:
        return default

def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def normalize_date(x) -> Optional[date]:
    """Retourne un objet date (ou None)."""
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    s = str(x).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


def weekday_fr(d: date) -> str:
    names = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    return names[d.weekday()]


def all_records(table) -> List[Dict[str, Any]]:
    try:
        return table.all()
    except Exception:
        return []


def log_event(record_id: str, event: str, level: str = "info", payload: Optional[dict] = None):
    if TAB_LOGS is None:
        return
    try:
        TAB_LOGS.create({
            "Record ID": record_id,
            "Event": event,
            "Level": level,
            "Payload": json.dumps(payload or {}, ensure_ascii=False)
        })
    except Exception:
        pass


def normalize_lookup_number(v, default=None):
    if isinstance(v, list):
        if not v:
            return default
        return to_int(v[0], default if default is not None else 0)
    if v in (None, ""):
        return default
    return to_int(v, default if default is not None else 0)

DAY_ORDER = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

def best_spacing(jours_dispo, nb_final, jours_proposes):
    """
    Calcule une répartition cohérente des jours de séances.
    Règles : 
    - Alignement prioritaire sur Jours_proposés
    - Tolérance de 1 enchaînement max
    """

    # 1) Normalisation (majuscules / accents identiques à Airtable)
    jours_dispo = [j.strip() for j in jours_dispo]
    jours_proposes = [j.strip() for j in jours_proposes]

    # 2) Si déjà le bon nombre → on trie dans l’ordre recommandé
    if len(jours_dispo) == nb_final:
        return sorted(jours_dispo, key=lambda j: jours_proposes.index(j) if j in jours_proposes else 99)

    # 3) Si trop de jours → on garde ceux alignés avec la référence
    if len(jours_dispo) > nb_final:
        tri = sorted(jours_dispo, key=lambda j: jours_proposes.index(j) if j in jours_proposes else 99)
        return tri[:nb_final]

    # 4) Si pas assez de jours → on complète avec les meilleurs jours possibles
    final = list(jours_dispo)
    for j in jours_proposes:
        if len(final) >= nb_final:
            break
        if j not in final:
            final.append(j)

    # 5) Vérification enchaînement : max 1 consécutif
    # (L’ordre logique des jours -> Lundi,...,Dimanche)
    ordre = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    final_sorted = sorted(final, key=lambda j: ordre.index(j))

    return final_sorted

def normalize_phase(phase: str) -> str:
    if not phase:
        return "base"

    p = phase.lower()

    if any(x in p for x in ["base", "fond"]):
        return "base"

    if any(x in p for x in ["pro", "dev", "spéc", "spec", "prépa", "progress"]):
        return "developpement"

    if "aff" in p:
        return "affutage"

    if "course" in p:
        return "course"

    return "base"  # fallback safe

def build_weekly_message(phase: str, niveau: str, objectif: str, semaine: int, nb_semaines: int) -> str:
    phase_type = normalize_phase(phase)

    blocs = []

    # Ton général par phase
    if phase_type == "base":
        blocs.append("On construit les bases tranquillement, sans forcer. Le but est d’installer des sensations stables.")
    elif phase_type == "developpement":
        blocs.append("On intensifie doucement mais sûrement. L’objectif est de progresser sans brûler les étapes.")
    elif phase_type == "affutage":
        blocs.append("On commence à alléger un peu la charge pour arriver frais le jour J. On écoute les sensations.")
    elif phase_type == "course":
        blocs.append("C’est la dernière ligne droite. On ne cherche plus à progresser, juste à être prêt et confiant.")

    # Personnalisation selon objectif
    if objectif:
        blocs.append(f"Ton objectif **{objectif}** reste le fil directeur.")

    # Personnalisation selon niveau
    if niveau.lower() in ["débutant", "reprise"]:
        blocs.append("Rappelle-toi : priorité à la respiration confortable. Si ça souffle trop → on ralentit.")
    elif niveau.lower() in ["intermédiaire", "confirmé"]:
        blocs.append("Tu peux te concentrer sur l’efficacité du geste : cadence fluide, relâchement des épaules.")

    # Encouragement dynamique
    progression = int((semaine / nb_semaines) * 100)
    if progression < 30:
        blocs.append("Tu es en train de construire quelque chose. Continue sans te précipiter. 💛")
    elif progression < 70:
        blocs.append("Tu es dans le cœur de la progression. Tu gères ça avec constance 👣")
    else:
        blocs.append("Tu as déjà fait le plus dur. Maintenant, on sécurise et on garde confiance ✨")

    # Final
    return "\n\n".join(blocs)

def lookup_message_hebdo(phase: str, niveau: str, objectif: str) -> Optional[str]:
    for rec in TAB_MESSAGES.values():
        f = rec.get("fields", {})
        if (
            f.get("Phase") == phase
            and f.get("Niveau") == niveau
            and f.get("Objectif") == objectif
        ):
            return f.get("Message_Final", "")
    return None

# helpers_reference.py

def lookup_reference_jours(cf):
    """
    Lookup table Référence Jours optimisée par clé_niveau_reference
    Retourne : dict { Nb_jours_min, Nb_jours_max, Jours_proposés }
    """

    key = cf.get("Clé_niveau_reference")  # Ex: "Running-Intermédiaire-10K"
    if not key:
        return None

    row = TAB_REF_JOURS.find("Clé_niveau_reference", key)
    if not row:
        return None

    fields = row["fields"]
    return {
        "Nb_jours_min": fields.get("Nb_jours_min", 0),
        "Nb_jours_max": fields.get("Nb_jours_max", 0),
        "Jours_proposés": fields.get("Jours_proposés", []),
    }

def lookup_reference_jours(cf):
    """
    Retourne les paramètres Jours_min, Jours_max, Jours_proposés
    depuis la table Airtable 'Référence Jours' en fonction du profil.
    """
    mode = cf.get("Mode", "").strip()
    niveau = cf.get("Niveau", "").strip()
    objectif = cf.get("Objectif", "").strip()

    # Clé utilisée dans Airtable
    key = f"{mode}-{niveau}-{objectif}"

    # Nom EXACT de la table (à vérifier si emojis ou espaces diffèrent)
    table_name = "Référence Jours"

    # On recherche la ligne correspondant à la clé
    rows = airtable_get_all(table_name, formula=f"{{Clé_niveau_reference}} = '{key}'")

    # Pas trouvé → erreur contrôlée
    if not rows:
        return None

    row = rows[0]["fields"]

    # Extraction propre
    jours_min = row.get("Nb_jours_min")
    jours_max = row.get("Nb_jours_max")
    jours_proposes = row.get("Jours_proposés", [])

    # Normalisation (si multi-select, on obtient une liste de labels)
    if isinstance(jours_proposes, str):
        jours_proposes = [jours_proposes]

    return {
        "jours_min": int(jours_min) if jours_min is not None else None,
        "jours_max": int(jours_max) if jours_max is not None else None,
        "jours_proposés": jours_proposes
    }

# -----------------------------------------------------------------------------
# SCN_01 — Étape 2 : Contrôle jours disponibles
# -----------------------------------------------------------------------------

def check_days_and_level(cf: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Contrôle B03-COH-03/04/05/06.
    Retour: (ok, payload_erreur_ou_vide)
    """
    # Nb jours dispo : liste de jours → compter
    jdispo = fget(cf, F_JOURS_LIST)
    if isinstance(jdispo, list):
        nb = len(jdispo)
    elif isinstance(jdispo, (int, float, str)):
        nb = to_int(jdispo, 0)
    else:
        nb = 0

    niv = fget(cf, F_NIVEAU, "Reprise")
    jmin = to_int(fget(cf, F_JOURS_MIN, None), None)
    jmax = to_int(fget(cf, F_JOURS_MAX, None), None)

    # zéros / None
    if nb == 0:
        return False, {
            "status": "error",
            "error": "days_zero",
            "message_id": "SC_COACH_023",
            "message": "⛔️ Aucun jour disponible sélectionné.",
            "niveau": niv,
            "nb_jours": nb
        }

    # Si référentiel absent → on laisse passer (pas de blocage arbitraire)
    if jmin is None and jmax is None:
        return True, {}

    if jmin is not None and nb < jmin:
        return False, {
            "status": "error",
            "error": "days_below_min",
            "message_id": "SC_COACH_021",
            "message": f"⛔️ {nb}j/semaine < minimum ({jmin}) pour le niveau {niv}.",
            "niveau": niv,
            "nb_jours": nb,
            "min": jmin
        }

    if jmax is not None and nb > jmax:
        return False, {
            "status": "error",
            "error": "days_above_max",
            "message_id": "SC_COACH_022",
            "message": f"⛔️ {nb}j/semaine > maximum ({jmax}) pour le niveau {niv}.",
            "niveau": niv,
            "nb_jours": nb,
            "max": jmax
        }

    # Incohérence « rituel » (option simple) : Débutant >=6 j/semaine
    if str(niv).lower() in ("débutant", "debutant", "reprise") and nb >= 6:
        return False, {
            "status": "error",
            "error": "days_rituel_incoherent",
            "message_id": "SC_COACH_024",
            "message": "⛔️ Incohérence: trop de jours pour le niveau. Réduis et réessaie.",
            "niveau": niv,
            "nb_jours": nb
        }

    return True, {
    "nb_jours": nb,
    "jours_dispo": jdispo   # ← on ajoute la vraie liste de jours
}


# -----------------------------------------------------------------------------
# SCN_01 — Étape 3 : Quota
# -----------------------------------------------------------------------------

from datetime import datetime

def check_quota(coureur):
    f = coureur.get("fields", {})

    # 1) Groupe du coureur
    groupe_list = f.get("Groupe", [])
    if not groupe_list:
        return True, None  # Pas de groupe = pas de quota

    groupe_id = groupe_list[0]  # Airtable linked record ID

    # 2) Lecture de la fiche Groupe
    g = TAB_GROUPES.get(groupe_id)
    if not g:
        return True, None

    gf = g.get("fields", {})
    nom_groupe = gf.get("Nom du groupe", "?")
    quota = gf.get("Quota mensuel", 999) or 999  # fallback safe
    autorise = gf.get("Autoriser génération", True)

    # Blocage dur si groupe interdit
    if isinstance(autorise, bool) and not autorise:
        return False, {
            "status": "error",
            "error": "quota_exceeded",
            "message_id": "SC_COACH_031",
            "message": f"⛔️ Génération interdite pour le groupe **{nom_groupe}**.",
            "quota_mensuel": quota,
        }

    # 3) Comptage du nombre de générations du groupe ce mois-ci
    current_month = datetime.now().strftime("%Y-%m")
    count = 0
    for rec in TAB_SUIVI.values():
        sf = rec.get("fields", {})
        if groupe_id in (sf.get("Groupe") or []):
            date_gen = sf.get("Date génération", "")
            if current_month in date_gen:
                if sf.get("Statut") == "success":
                    count += 1

    # 4) Comparaison au quota
    if count >= quota:
        return False, {
            "status": "error",
            "error": "quota_exceeded",
            "message_id": "SC_COACH_031",
            "message": f"🚫 Le quota mensuel du groupe **{nom_groupe}** est atteint ({quota}/{quota}).",
            "groupe": nom_groupe,
            "quota": quota,
            "used": count
        }

    return True, None

# -----------------------------------------------------------------------------
# Phases & Types
# -----------------------------------------------------------------------------

def fetch_param_phases() -> List[Dict[str, Any]]:
    recs = all_records(TAB_PARAM)
    items = []
    for r in recs:
        f = r.get("fields", {})
        items.append({
            "id": r.get("id"),
            "Nom phase": f.get("Nom phase") or f.get("Phase") or f.get("ID_Phase") or "",
            "Ordre": to_int(f.get("Ordre"), 999),
            "Nb séances max / semaine": to_int(f.get("Nb séances max / semaine"), DEFAULT_JOURS_SEMAINE)
        })
    items.sort(key=lambda x: x["Ordre"])
    return items


def filter_types(phase: str, mode: str, objectif: Optional[str], niveau: Optional[str]) -> List[Dict[str, Any]]:
    out = []
    for r in all_records(TAB_TYPES):
        f = r.get("fields", {})
        f_mode = f.get("Mode") or DEFAULT_MODE
        f_phase = f.get("Phase") or f.get("Nom phase")
        if not f_phase:
            continue
        if str(f_mode).lower().strip() != str(mode).lower().strip():
            continue
        if str(f_phase).lower().strip() != str(phase).lower().strip():
            continue
        if objectif:
            f_obj = f.get("Objectif") or f.get("Objectifs compatibles")
            if f_obj:
                if isinstance(f_obj, list):
                    if not any(str(objectif).lower() == str(x).lower() for x in f_obj):
                        continue
                else:
                    if str(objectif).lower() not in str(f_obj).lower():
                        continue
        if niveau:
            f_niv = (
                f.get("Niveau")
                or f.get("Niveaux compat.")
                or f.get("Niveau (plage)")
                or f.get("Niveaux compatibles")
            )
            if f_niv:
                if isinstance(f_niv, list):
                    if not any(str(niveau).lower() == str(x).lower() for x in f_niv):
                        continue
                else:
                    if str(f_niv).strip() and str(niveau).lower() != str(f_niv).lower():
                        continue
        out.append({
            "id": r.get("id"),
            "Clé séance": f.get("Clé séance"),
            "Nom séance": f.get("Nom séance") or "Séance",
            "Durée (min)": to_int(f.get("Durée (min)"), 0),
            "Charge": f.get("Charge"),
            "Message coach": f.get("Message coach"),
            "Message hebdo": f.get("Message hebdo"),
            "Type séance (court)": f.get("Type séance (court)")
        })
    return out

def pick_progressive_load(candidates, week, session_index):
    """
    Sélectionne une séance en progressivité :
    - Semaine après semaine : charge croissante
    - À volume égal : alternance de stimulus
    """
    # Tri par charge d'abord
    sorted_cands = sorted(
        candidates,
        key=lambda c: (
            c.get("Charge", 1),
            c.get("Durée (min)", 0)
        )
    )

    # Index basé sur semaine + position dans la semaine
    pos = (week * 2 + session_index) % len(sorted_cands)
    return sorted_cands[pos]

def pick_deterministic(cands: List[Dict[str, Any]], week_index: int, index_in_week: int) -> Optional[Dict[str, Any]]:
    if not cands:
        return None
    idx = (week_index * 2 + index_in_week) % len(cands)
    return cands[idx]

# -----------------------------------------------------------------------------
# Archivage versionné (move → Archives Séances)
# -----------------------------------------------------------------------------

def move_previous_version_to_archives(record_id: str, current_version: int) -> int:
    """Copie les séances de la version courante vers T_ARCHIVES puis supprime de T_SEANCES.
    Retourne le nombre d'éléments archivés. Si table archives absente → fallback Archive=True.
    """
    count = 0
    try:
        recs = TAB_SEANCES.all(formula=f"AND({{Version plan}}={current_version}, FIND('{record_id}', ARRAYJOIN({{Coureur}})))")
        if not recs:
            return 0
        if TAB_ARCHIVES_T:
            for r in recs:
                f = r.get("fields", {})
                # mapping simple; adapter si d'autres champs spécifiques à l'archive
                archive_fields = {k: v for k, v in f.items()}
                archive_fields.pop("id", None)
                archive_fields["Archive de"] = [record_id]
                TAB_ARCHIVES_T.create(archive_fields)
                TAB_SEANCES.delete(r["id"])  # suppression après copie
                count += 1
        else:
            # Fallback: flag Archive=True si le champ existe
            for r in recs:
                f = r.get("fields", {})
                if "Archive" in f and not f.get("Archive"):
                    TAB_SEANCES.update(r["id"], {"Archive": True})
                    count += 1
    except Exception as e:
        log_event(record_id, "archive_move_failed", level="error", payload={"error": str(e)})
        raise
    return count

# -----------------------------------------------------------------------------
# Semaine de course : VEILLE & RACE
# -----------------------------------------------------------------------------

def ensure_race_and_veille_in_last_week(
    semaine_seances: List[Dict[str, Any]],
    date_course: date,
    mode: str,
    niveau: Optional[str],
    objectif: Optional[str]
):
    if not semaine_seances:
        return

    by_date = { s["Date"]: s for s in semaine_seances }

    cands_course = filter_types("Course", mode, objectif, niveau)
    race_model = next((c for c in cands_course if c.get("Clé séance") and "RACE" in str(c["Clé séance"]).upper()), None)
    veille_model = next((c for c in cands_course if c.get("Clé séance") and "VEILLE" in str(c["Clé séance"]).upper()), None)

    # RACE (Jour J)
    race_day = date_course
    if race_day not in by_date:
        semaine_seances.sort(key=lambda s: abs((s["Date"] - race_day).days))
        moved = semaine_seances[0]
        old = moved["Date"]
        moved["Date"] = race_day
        by_date.pop(old, None)
        by_date[race_day] = moved

    race_slot = by_date[race_day]
    if race_model:
        race_slot.update({
            "Clé séance": race_model["Clé séance"],
            "Nom séance": race_model["Nom séance"] or "Séance",
            "Durée (min)": race_model["Durée (min)"],
            "Charge": race_model["Charge"],
            "Type séance (court)": race_model.get("Type séance (court)"),
            "Message coach": race_model.get("Message coach"),
            "Message hebdo": race_model.get("Message hebdo"),
            "Phase": "Course"
        })

    # VEILLE (J-1)
    veille_day = race_day - timedelta(days=1)
    pre = [s for s in semaine_seances if s["Date"] < race_day]
    pre.sort(key=lambda s: s["Date"], reverse=True)
    if pre:
        veille_slot = pre[0]
        veille_slot["Date"] = veille_day
        if veille_model:
            veille_slot.update({
                "Clé séance": veille_model["Clé séance"],
                "Nom séance": veille_model["Nom séance"] or "Séance",
                "Durée (min)": veille_model["Durée (min)"],
                "Charge": veille_model["Charge"],
                "Type séance (court)": veille_model.get("Type séance (court)"),
                "Message coach": veille_model.get("Message coach"),
                "Message hebdo": veille_model.get("Message hebdo"),
                "Phase": "Course"
            })
    else:
        all_sorted = sorted(semaine_seances, key=lambda s: s["Date"]) or []
        if all_sorted:
            cand = all_sorted[0]
            cand["Date"] = veille_day
            if veille_model:
                cand.update({
                    "Clé séance": veille_model["Clé séance"],
                    "Nom séance": veille_model["Nom séance"] or "Séance",
                    "Durée (min)": veille_model["Durée (min)"],
                    "Charge": veille_model["Charge"],
                    "Type séance (court)": veille_model.get("Type séance (court)"),
                    "Message coach": veille_model.get("Message coach"),
                    "Message hebdo": veille_model.get("Message hebdo"),
                    "Phase": "Course"
                })

# -----------------------------------------------------------------------------
# Flask App
# -----------------------------------------------------------------------------

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def health():
    return "SmartCoach API up (SCN_01)", 200


@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    try:
        body = request.get_json(force=True, silent=True) or {}
        record_id = body.get("record_id")
        if not record_id:
            return jsonify({"error": "record_id manquant"}), 400

        # Champs SCN_01 (prioritaires s'ils sont fournis)
        date_debut_plan = normalize_date(body.get("date_debut_plan"))
        date_fin_plan = normalize_date(body.get("date_fin_plan"))

        # Optionnels (fallback legacy)
        nb_semaines_input = body.get("nb_semaines")
        jours_par_semaine_input = body.get("jours_par_semaine")

# -----------------------------------------------------------------------------
#                   1. CHARGER LE COUREUR
# -----------------------------------------------------------------------------
        coureur = TAB_COUR.get(record_id)
        if not coureur or "fields" not in coureur:
            return jsonify({"error": "Coureur introuvable"}), 404
        cf = coureur["fields"]

# -----------------------------------------------------------------------------
#                   2. CALCUL & VALIDATION DES JOURS
# -----------------------------------------------------------------------------
        ctx = {}

        ok_days, payload_days = check_days_and_level(cf)
        if not ok_days:
            log_event(record_id, "days_control_failed", level="warning", payload=payload_days)
            return jsonify(payload_days), 400
            
        # ✅ Jours disponibles validés par B03-COH
        jours_dispo = cf.get("📅 Jours disponibles") or cf.get("Jours disponibles") or []

        # Normalisation : toujours une liste propre
        if isinstance(jours_dispo, str):
            jours_dispo = [j.strip() for j in jours_dispo.split(",")]

        jours_dispo = [j for j in jours_dispo if j]  # nettoyage

        # Nombre final de jours à utiliser
        nb = clamp(len(jours_dispo), jours_min, jours_max)

        if nb == 0:
            return jsonify({
                "error": "days_zero",
                "message": "⛔️ Aucun jour disponible sélectionné.",
                "message_id": "SC_COACH_023",
                "nb_jours": 0,
                "niveau": cf.get("Niveau"),
                "status": "error"
            }), 400

# -----------------------------------------------------------------------------
#                   2b. CONSTRUCTION COHERENTE DE JOURS_FINAL
# -----------------------------------------------------------------------------

        def normalize(day):
            # Sécurise l'écriture (ex : "Dimanche" vs "dimanche")
            return day.strip().capitalize()

        # Normalisation données utilisateur
        jours_dispo = [normalize(d) for d in jours_dispo]

        # Normalisation référence
        jours_proposes = [normalize(d) for d in jours_proposes]

        # 1) Déterminer nb de séances final
        nb = clamp(len(jours_dispo), jours_min, jours_max)

        # 2) Si trop de jours → tri selon l'ordre dans jours_proposés
        if len(jours_dispo) > nb:
            jours_final = [j for j in jours_proposes if j in jours_dispo][:nb]
        else:
            # 3) Sinon on prend tous les jours saisis
            jours_final = list(jours_dispo)

        # 4) Si pas assez de jours → compléter avec la séquence idéale
        if len(jours_final) < nb:
            for j in jours_proposes:
                if j not in jours_final:
                    jours_final.append(j)
                if len(jours_final) == nb:
                    break

        # 5) Règle : jamais plus de 2 séances consécutives
        # (ex traitement Dimanche → Lundi inclus)
        jours_semaine = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

        def distance(a, b):
            return (jours_semaine.index(b) - jours_semaine.index(a)) % 7

        for i in range(len(jours_final)):
            # si 3 jours d'affilée → on remplace le central par repos / EF
            prev = jours_final[i-1]
            curr = jours_final[i]
            nxt = jours_final[(i+1) % len(jours_final)]
            if distance(prev, curr) == 1 and distance(curr, nxt) == 1:
                # on remplace par un jour proposé suivant qui n'est pas consécutif
                for candidate in jours_proposes:
                    if candidate not in jours_final:
                        jours_final[i] = candidate
                        break

        # jours_final est maintenant prêt :
        ctx["jours_final"] = jours_final

        
# -----------------------------------------------------------------------------
#                   3. CONTRÔLE DU GROUPE
# -----------------------------------------------------------------------------
        # ✅ Lookup référence jours selon Mode + Niveau + Objectif
        cf = cour.get("fields", {})
        ref = lookup_reference_jours(cf)
        if not ref:
            return {
                "status": "error",
                "error": "reference_not_found",
                "message": "⛔ Profil non trouvé dans Référence Jours.",
                "message_id": "SC_COACH_024"
            }

        if not ref:
            return jsonify({
                "error": "reference_not_found",
                "message": "⛔ Profil non trouvé dans Référence Jours.",
                "message_id": "SC_COACH_024"
            }), 400

        jours_min = ref["jours_min"]
        jours_max = ref["jours_max"]
        jours_proposes = ref["jours_proposés"]
        
        groupe = cf.get("Groupe", [])

        if not groupe:
            # 🆕 Nouveau coureur → on le place dans le groupe 'Autres'
            default_group = TAB_GROUPES.find("Nom du groupe", "Autres")
            if default_group:
                TAB_COUR.update(record_id, {"Groupe": [default_group["id"]]})
                log_event(record_id, "groupe_assigned", payload={"groupe": "Autres"})
        else:
            # ✅ Groupe déjà en place → ne rien modifier
            log_event(record_id, "groupe_ok", payload={"groupe": groupe[0]["id"] if isinstance(groupe, list) else groupe})

# -----------------------------------------------------------------------------
#                   4. VERIFIER QUOTA
# -----------------------------------------------------------------------------
        ok_quota, refusal = check_quota(coureur)
        if not ok_quota:
            log_event(record_id, "quota_refused", level="warning", payload=refusal)
            return jsonify(refusal), 429

        # Inputs coureur usuels
        mode = fget(cf, F_MODE, DEFAULT_MODE) or DEFAULT_MODE

        # Normalisation Objectif (multi-select → string)
        objectif_raw = fget(cf, F_OBJECTIF)
        if isinstance(objectif_raw, list):
            objectif = objectif_raw[0]
        else:
            objectif = objectif_raw

        niveau = fget(cf, F_NIVEAU)

        # Nettoyage sécurité
        mode = str(mode).strip()
        niveau = str(niveau).strip()
        objectif = str(objectif).strip()

        # Type de plan (pour suivi usage)
        type_plan = f"{mode} – {niveau} – {objectif}"

        # Loger l'information dans le suivi génération (table Suivi génération Airtable)
        log_event(
            record_id,
            "plan_type",
            level="info",
            payload={
                "type_plan": type_plan,
                "mode": mode,
                "niveau": niveau,
                "objectif": objectif
            }
        )

# -----------------------------------------------------------------------------
#                   5. CALCUL DUREE DU PLAN
# -----------------------------------------------------------------------------
        if date_debut_plan and date_fin_plan and date_fin_plan >= date_debut_plan:
            delta = (date_fin_plan - date_debut_plan).days
            nb_semaines = max(1, delta // 7)
            start_date = date_debut_plan
        else:
            # fallback legacy: depuis la date de course
            if not date_course:
                date_course = (datetime.utcnow() + timedelta(days=30)).date()
            if nb_semaines_input is not None:
                nb_semaines = to_int(nb_semaines_input, DEFAULT_WEEKS)
            else:
                delta_days = max(0, (date_course - date.today()).days)
                nb_semaines = max(1, delta_days // 7)
                if nb_semaines < 4:
                    nb_semaines = 4
                if nb_semaines > 24:
                    nb_semaines = 24
            start_date = (date_course - timedelta(weeks=nb_semaines))
        # Gel de la durée
        nb_semaines = max(1, nb_semaines)

        # Jours par semaine
        if jours_par_semaine_input is not None:
            jours_par_semaine = to_int(jours_par_semaine_input, DEFAULT_JOURS_SEMAINE)
        else:
            jours_par_semaine = max(1, min(6, nb_jours_dispo))

# -----------------------------------------------------------------------------
#                   6. ARCHIVER VERSION PRECEDENTE
# -----------------------------------------------------------------------------
        current_version = to_int(cf.get("Version plan"), 0)
        try:
            archived = move_previous_version_to_archives(record_id, current_version)
            log_event(record_id, "archived_previous_version", payload={"count": archived, "version": current_version})
        except Exception as e:
            # SC_COACH_041 : on stoppe proprement (admin-only)
            return jsonify({
                "status": "error",
                "error": "archive_failed",
                "message_id": "SC_COACH_041",
                "message": f"⛔️ Archivage impossible: {str(e)}"
            }), 500

# -----------------------------------------------------------------------------
#                   7. CONSTRUIRE LA GRILLE S x JOURS_FINAL
# -----------------------------------------------------------------------------
        phases = fetch_param_phases() or [
            {"Nom phase": "Base1", "Ordre": 1, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Base2", "Ordre": 2, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Prépa spécifique", "Ordre": 3, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Course", "Ordre": 4, "Nb séances max / semaine": jours_par_semaine},
        ]

        # Offsets dynamiques via Jours_final
        DAY_ORDER = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
        if ctx.get("jours_final"):
            offsets = [DAY_ORDER.index(j) for j in ctx["jours_final"]]
        else:
            # Fallback sécurité (ne doit pas arriver si SCN_01 bien appliqué)
            offsets = [DAY_ORDER.index(j) for j in (cf.get("Jours_proposés") or ["Mercredi","Samedi"])]


        # Timeline des phases : dernière semaine = Course
        phase_names = [p["Nom phase"] for p in phases]
        base_weeks = max(1, nb_semaines - 1)
        non_course = [p for p in phase_names if str(p).lower() != "course"]
        share = max(1, base_weeks // max(1, len(non_course)))
        phase_timeline: List[str] = []
        cursor = 0
        for p in phases:
            name = p["Nom phase"]
            if str(name).lower() == "course":
                continue
            count = share
            if cursor + count > base_weeks:
                count = max(1, base_weeks - cursor)
            for _ in range(count):
                phase_timeline.append(name)
            cursor += count
        while len(phase_timeline) < nb_semaines - 1:
            phase_timeline.append(non_course[-1] if non_course else "Base2")
        phase_timeline.append("Course")
        phase_timeline = phase_timeline[:nb_semaines]

# -----------------------------------------------------------------------------
#                   8. SELECTION DES SEANCES TYPES
# -----------------------------------------------------------------------------
        def candidates_with_fallback(phase_for_pick: str, niv: str) -> List[Dict[str, Any]]:
            cands = filter_types(phase_for_pick, mode, objectif, niv)
            if cands:
                return cands
            # fallback niveau -1 (naïf): on tente une version plus "basse"
            lower = {
                "Elite": "Avancé",
                "Avancé": "Intermédiaire",
                "Intermédiaire": "Débutant",
                "Débutant": "Reprise",
                "Reprise": None
            }.get(niv, None)
            if lower:
                return filter_types(phase_for_pick, mode, objectif, lower)
            return []

        created = 0
        created_ids: List[str] = []
        preview: List[Dict[str, Any]] = []
        version_next = current_version + 1

        week_buckets: Dict[int, List[Dict[str, Any]]] = {}
        for w in range(nb_semaines):
            week_buckets[w] = []
            monday = start_date + timedelta(weeks=w)
            phase = phase_timeline[w]
            for j_index, off in enumerate(offsets[:jours_par_semaine]):
                d = monday + timedelta(days=off)
                phase_for_pick = phase
                if str(phase).lower() in ("prépa générale", "prepa generale", "base"):
                    phase_for_pick = "Base1" if (w % 2 == 0) else "Base2"
                cands = candidates_with_fallback(phase_for_pick, niveau)
                if not cands:
                    # SC_COACH_061 : profil non couvert
                    return jsonify({
                        "status": "error",
                        "error": "no_session_found",
                        "message_id": "SC_COACH_061",
                        "message": f"⛔️ Aucune séance trouvée pour Phase={phase_for_pick}, Niveau={niveau}, Objectif={objectif}.",
                        "week": w + 1,
                        "date": d.isoformat()
                    }), 400
                st = pick_progressive_load(cands, w, j_index)
                week_buckets[w].append({
                    "Date": d,
                    "Semaine": w + 1,
                    "Phase": phase,
                    "Clé séance": st.get("Clé séance"),
                    "Nom séance": st.get("Nom séance") or "Séance",
                    "Durée (min)": st.get("Durée (min)"),
                    "Charge": st.get("Charge"),
                    "Type séance (court)": st.get("Type séance (court)"),
                    "Message coach": st.get("Message_coach (modèle)")
                })                

        # Semaine "Course"
        if date_course and week_buckets.get(nb_semaines - 1):
            ensure_race_and_veille_in_last_week(
                semaine_seances=week_buckets[nb_semaines - 1],
                date_course=date_course,
                mode=mode,
                niveau=niveau,
                objectif=objectif
            )

# -----------------------------------------------------------------------------
#                   9. INSERTION + SÛRETE
# -----------------------------------------------------------------------------
        try:
            for w in range(nb_semaines):
                for s in week_buckets[w]:
                    fields_new = {
                        "Coureur": [record_id],
                        "Date": s["Date"].isoformat(),
                        "Jour planifié": weekday_fr(s["Date"]),
                        "Semaine": s["Semaine"],
                        "Phase": s["Phase"],
                        "Clé séance": s.get("Clé séance"),
                        "Nom séance": s.get("Nom séance"),
                        "Durée (min)": s.get("Durée (min)"),
                        "Charge": s.get("Charge"),
                        "Type séance (court)": s.get("Type séance (court)"),
                        "Message coach": s.get("Message coach"),
                        "Message hebdo": s.get("Message hebdo"),
                        "Version plan": version_next
                    }
                    created_rec = TAB_SEANCES.create(fields_new)
                    created += 1
                    created_ids.append(created_rec["id"])  # pour rollback
                    if len(preview) < 50:
                        preview.append(fields_new.copy())
        except Exception as e:
            # Rollback (SC_COACH_071)
            for rid in created_ids:
                try:
                    TAB_SEANCES.delete(rid)
                except Exception:
                    pass
            log_event(record_id, "create_failed_rollback", level="error", payload={"error": str(e), "created": created})
            return jsonify({
                "status": "error",
                "error": "create_failed",
                "message_id": "SC_COACH_071",
                "message": f"⛔️ Erreur lors de la création des séances — rollback effectué ({created} items supprimés)."
            }), 500

        # Incrément version si création effective
        if created > 0:
            try:
                TAB_COUR.update(record_id, {"Version plan": version_next})
                log_event(record_id, "version_plan_incremented", payload={"to": version_next})
            except Exception as e:
                log_event(record_id, "version_plan_increment_failed", level="error", payload={"error": str(e)})

        TAB_SUIVI.create({
            "Coureur": [record_id],
            "Groupe": cf.get("Groupe"),
            "Date génération": datetime.now().isoformat(),
            "Statut": "success",
            "Type plan": mode,
        })

        msg = f"✅ Nouveau plan généré — **Version {version_next}**\n{created} séances créées."
        return jsonify({
            "status": "ok",
            "message_id": "SC_OK_200",
            "message": msg,
            "nb_semaines": nb_semaines,
            "jours_par_semaine": jours_par_semaine,
            "version_plan": version_next,
            "total": created,
            "preview": preview
        }), 200

    except Exception as e:
        rid = None
        try:
            rid = (request.get_json(silent=True) or {}).get("record_id")
        except Exception:
            pass
        log_event(rid or "unknown", "generation_failed", level="error", payload={"error": str(e), "trace": traceback.format_exc()})
        return jsonify({"status": "error", "error": "internal_error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=True)
