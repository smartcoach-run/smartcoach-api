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

# Ouverture tables
TAB_COUR    = api.table(BASE_ID, T_COUR)
TAB_SEANCES = api.table(BASE_ID, T_SEANCES)
TAB_TYPES   = api.table(BASE_ID, T_TYPES)
TAB_PARAM   = api.table(BASE_ID, T_PARAM)

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

    return True, {"nb_jours": nb}

# -----------------------------------------------------------------------------
# SCN_01 — Étape 3 : Quota
# -----------------------------------------------------------------------------

def check_quota(cour: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    f = cour.get("fields", {})
    version = to_int(f.get("Version plan"), 0)

    # Quota côté Coureur (lookup possible)
    quota = normalize_lookup_number(f.get("Quota mensuel"), None)

    # Override via Groupe (si présent)
    try:
        if TAB_GROUPES and f.get("Groupe"):
            gid = None
            if isinstance(f["Groupe"], list) and f["Groupe"]:
                gid = f["Groupe"][0]
            if gid:
                g = TAB_GROUPES.get(gid)
                gf = g.get("fields", {})
                qg = normalize_lookup_number(gf.get("Quota mensuel"), None)
                if qg is not None and qg > 0:
                    quota = qg
                autorise = gf.get("Autoriser génération")
                if isinstance(autorise, bool) and not autorise:
                    return False, {
                        "status": "error",
                        "error": "quota_exceeded",
                        "message_id": MESSAGE_ID_QUOTA,
                        "message": "⛔️ Génération interdite par le groupe.",
                        "version_plan": version,
                        "quota_mensuel": quota if quota is not None else 0
                    }
    except Exception:
        pass

    if quota is None:
        quota = 999

    if version >= quota:
        return False, {
            "status": "error",
            "error": "quota_exceeded",
            "message_id": MESSAGE_ID_QUOTA,
            "message": "⛔️ Quota mensuel atteint — génération refusée.",
            "version_plan": version,
            "quota_mensuel": quota
        }
    return True, {}

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

        # 1) Coureur
        coureur = TAB_COUR.get(record_id)
        if not coureur or "fields" not in coureur:
            return jsonify({"error": "Coureur introuvable"}), 404
        cf = coureur["fields"]

        # 2) Contrôle jours disponibles
        ok_days, payload_days = check_days_and_level(cf)
        if not ok_days:
            log_event(record_id, "days_control_failed", level="warning", payload=payload_days)
            return jsonify(payload_days), 400
        # Nombre de jours retenu
        nb_jours_dispo = payload_days.get("nb_jours") or 1

        # 3) Quota
        ok_quota, refusal = check_quota(coureur)
        if not ok_quota:
            log_event(record_id, "quota_refused", level="warning", payload=refusal)
            return jsonify(refusal), 429

        # Inputs coureur usuels
        mode = fget(cf, F_MODE, DEFAULT_MODE) or DEFAULT_MODE
        objectif = fget(cf, F_OBJECTIF, "10K")
        niveau = fget(cf, F_NIVEAU, "Reprise")
        date_course = normalize_date(fget(cf, F_DATE_COURSE))

        # 4) Calcul durée plan (priorité aux dates fournies)
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

        # 5) Archivage versionné
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

        # 6) Phases & Grille déterministe
        phases = fetch_param_phases() or [
            {"Nom phase": "Base1", "Ordre": 1, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Base2", "Ordre": 2, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Prépa spécifique", "Ordre": 3, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Course", "Ordre": 4, "Nb séances max / semaine": jours_par_semaine},
        ]

        # Offsets figés
        if jours_par_semaine == 1:
            offsets = [6]                  # Dim
        elif jours_par_semaine == 2:
            offsets = [4, 6]               # Ven, Dim
        elif jours_par_semaine == 3:
            offsets = [2, 4, 6]            # Mer, Ven, Dim
        elif jours_par_semaine == 4:
            offsets = [1, 3, 4, 6]         # Mar, Jeu, Ven, Dim
        else:
            offsets = [1, 2, 3, 4, 6][:jours_par_semaine]

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

        # 7) Sélection + fallback
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
                st = pick_deterministic(cands, w, j_index)
                week_buckets[w].append({
                    "Date": d,
                    "Semaine": w + 1,
                    "Phase": phase,
                    "Clé séance": st.get("Clé séance"),
                    "Nom séance": st.get("Nom séance") or "Séance",
                    "Durée (min)": st.get("Durée (min)"),
                    "Charge": st.get("Charge"),
                    "Type séance (court)": st.get("Type séance (court)"),
                    "Message coach": st.get("Message coach"),
                    "Message hebdo": st.get("Message hebdo")
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

        # 8) Écriture Airtable + rollback si échec partiel
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
