# -*- coding: utf-8 -*-
"""
SmartCoach API — main_v2.py
Version: 2025-11-11 (SCN_01 clean)

Pipeline SCN_01 :
1) Charger coureur
2) Contrôle jours (B03-COH-03/04/05/06)
3) Lookup Référence Jours -> (jours_min, jours_max, jours_proposés) + construire jours_final
4) Vérifier quota (RG-GEST-QUOTA)
5) Calcul durée plan (ou fallback date_course)
6) Archivage versionné
7) Grille S×J déterministe
8) Sélection séances types (+ fallback niveau -1)
9) Insertion + rollback en cas d’échec
"""

import os
import json
import traceback
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, date

from flask import Flask, request, jsonify
from pyairtable import Api

# Helpers locaux (tu peux les déplacer dans helpers.py si tu veux)
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

def fget(fields: Dict[str, Any], names: List[str], default=None):
    for n in names:
        if n in fields and fields[n] not in (None, ""):
            return fields[n]
    return default

# Imports projet
from airtable import airtable_get_all, airtable_get_one
from reference_jours import lookup_reference_jours  # 👉 on utilise la version module (pas de double définition)

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

AIRTABLE_KEY = os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID") or os.environ.get("BASE_ID")

if not AIRTABLE_KEY or not BASE_ID:
    raise RuntimeError("AIRTABLE_API_KEY / AIRTABLE_BASE_ID manquants.")

api = Api(AIRTABLE_KEY)

# Noms de tables
T_COUR = "👤 Coureurs"
T_SEANCES = "🏋️ Séances"
T_TYPES = "📘 Séances types"
T_PARAM = "⚙️ Paramètres phases"
T_MSGS = "📩 Messages Hebdo"           # aligné avec ta base
T_LOGS = "🧱 Logs SmartCoach"          # optionnel
T_GROUPES = "👥 Groupes"               # optionnel
T_ARCHIVES = "Archives Séances"        # optionnel
T_REF_JOURS = "⚖️ Référence Jours"
T_SUIVI = "📋 Suivi génération"

# Ouverture tables
TAB_COUR    = api.table(BASE_ID, T_COUR)
TAB_SEANCES = api.table(BASE_ID, T_SEANCES)
TAB_TYPES   = api.table(BASE_ID, T_TYPES)
TAB_PARAM   = api.table(BASE_ID, T_PARAM)
TAB_REF_JOURS = api.table(BASE_ID, T_REF_JOURS)
TAB_SUIVI   = api.table(BASE_ID, T_SUIVI)

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

# Tolérance noms de champs
F_DATE_COURSE = ["date_course", "Date course", "Date objectif", "Jour de course", "Date Objectif"]
F_OBJECTIF    = ["Objectif", "Objectif (normalisé)", "Objectif_normalisé", "Type objectif normalisé"]
F_NIVEAU      = ["Niveau", "Niveau (normalisé)", "Niveau_normalisé", "Niveau coach"]
F_MODE        = ["Mode", "Mode (normalisé)"]
F_JOURS_LIST  = ["Jours disponibles", "jours_disponibles", "Disponibilités"]
F_JOURS_MIN   = ["Nb_jours_min", "Nb_jours_min (calc)", "Jours_min"]
F_JOURS_MAX   = ["Nb_jours_max", "Nb_jours_max (calc)", "Jours_max"]

DAY_ORDER = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

# -----------------------------------------------------------------------------
# CONTRÔLES
# -----------------------------------------------------------------------------

def check_days_and_level(cf: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """B03-COH-03/04/05/06"""
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

    if nb == 0:
        return False, {
            "status": "error",
            "error": "days_zero",
            "message_id": "SC_COACH_023",
            "message": "⛔️ Aucun jour disponible sélectionné.",
            "niveau": niv,
            "nb_jours": nb
        }

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

    if str(niv).lower() in ("débutant", "debutant", "reprise") and nb >= 6:
        return False, {
            "status": "error",
            "error": "days_rituel_incoherent",
            "message_id": "SC_COACH_024",
            "message": "⛔️ Incohérence: trop de jours pour le niveau. Réduis et réessaie.",
            "niveau": niv,
            "nb_jours": nb
        }

    return True, {"nb_jours": nb, "jours_dispo": jdispo}

# -----------------------------------------------------------------------------
# QUOTA
# -----------------------------------------------------------------------------

def check_quota(coureur):
    f = coureur.get("fields", {})
    groupe_list = f.get("Groupe", [])
    if not groupe_list:
        return True, None  # pas de groupe = pas de quota

    groupe_id = groupe_list[0]  # linked record id
    g = TAB_GROUPES.get(groupe_id) if TAB_GROUPES else None
    if not g:
        return True, None

    gf = g.get("fields", {})
    nom_groupe = gf.get("Nom du groupe", "?")
    quota = gf.get("Quota mensuel", 999) or 999
    autorise = gf.get("Autoriser génération", True)

    if isinstance(autorise, bool) and not autorise:
        return False, {
            "status": "error",
            "error": "quota_exceeded",
            "message_id": "SC_COACH_031",
            "message": f"⛔️ Génération interdite pour le groupe **{nom_groupe}**."
        }

    current_month = datetime.now().strftime("%Y-%m")
    count = 0
    for rec in all_records(TAB_SUIVI):
        sf = rec.get("fields", {})
        if groupe_id in (sf.get("Groupe") or []):
            date_gen = sf.get("Date génération", "")
            if current_month in str(date_gen) and sf.get("Statut") == "success":
                count += 1

    if count >= quota:
        return False, {
            "status": "error",
            "error": "quota_exceeded",
            "message_id": "SC_COACH_031",
            "message": f"🚫 Quota mensuel du groupe **{nom_groupe}** atteint ({quota}/{quota}).",
            "groupe": nom_groupe,
            "quota": quota,
            "used": count
        }

    return True, None

# -----------------------------------------------------------------------------
# PARAM PHASES / TYPES
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
    sorted_cands = sorted(
        candidates,
        key=lambda c: (c.get("Charge", 1), c.get("Durée (min)", 0))
    )
    pos = (week * 2 + session_index) % len(sorted_cands)
    return sorted_cands[pos]

# -----------------------------------------------------------------------------
# ARCHIVAGE
# -----------------------------------------------------------------------------

def move_previous_version_to_archives(record_id: str, current_version: int) -> int:
    count = 0
    try:
        recs = TAB_SEANCES.all(formula=f"AND({{Version plan}}={current_version}, FIND('{record_id}', ARRAYJOIN({{Coureur}})))")
        if not recs:
            return 0
        if TAB_ARCHIVES_T:
            for r in recs:
                f = r.get("fields", {})
                archive_fields = {k: v for k, v in f.items()}
                archive_fields.pop("id", None)
                archive_fields["Archive de"] = [record_id]
                TAB_ARCHIVES_T.create(archive_fields)
                TAB_SEANCES.delete(r["id"])
                count += 1
        else:
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
# SEMAINE COURSE (VEILLE & RACE)
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

    # Jour J
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
# Flask
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

        # SCN_01 params
        date_debut_plan = normalize_date(body.get("date_debut_plan"))
        date_fin_plan = normalize_date(body.get("date_fin_plan"))
        nb_semaines_input = body.get("nb_semaines")
        jours_par_semaine_input = body.get("jours_par_semaine")

        # 1) Charger coureur
        coureur = TAB_COUR.get(record_id)
        if not coureur or "fields" not in coureur:
            return jsonify({"error": "Coureur introuvable"}), 404
        cf = coureur["fields"]

        # Date course (fallback legacy)
        date_course = normalize_date(fget(cf, F_DATE_COURSE))

        # 2) Contrôle jours + lookup référence + jours_final
        ok_days, payload_days = check_days_and_level(cf)
        if not ok_days:
            log_event(record_id, "days_control_failed", level="warning", payload=payload_days)
            return jsonify(payload_days), 400

        ref = lookup_reference_jours(cf)
        if not ref:
            return jsonify({
                "status": "error",
                "error": "reference_not_found",
                "message": "⛔ Profil non trouvé dans Référence Jours.",
                "message_id": "SC_COACH_024"
            }), 400

        jours_min = int(ref.get("jours_min", 0))
        jours_max = int(ref.get("jours_max", 7))
        jours_proposes = ref.get("jours_proposés", []) or []

        jours_dispo = cf.get("📅 Jours disponibles") or cf.get("Jours disponibles") or []
        if isinstance(jours_dispo, str):
            jours_dispo = [j.strip() for j in jours_dispo.split(",")]
        jours_dispo = [j for j in jours_dispo if j]

        def norm(d): return d.strip().capitalize()
        jours_dispo = [norm(d) for d in jours_dispo]
        jours_proposes = [norm(d) for d in jours_proposes]

        nb = clamp(len(jours_dispo), jours_min, jours_max)
        if nb == 0:
            return jsonify({
                "status": "error",
                "error": "days_zero",
                "message_id": "SC_COACH_023",
                "message": "⛔️ Aucun jour disponible sélectionné."
            }), 400

        if len(jours_dispo) > nb:
            jours_final = [j for j in jours_proposes if j in jours_dispo][:nb]
        else:
            jours_final = list(jours_dispo)

        if len(jours_final) < nb:
            for j in jours_proposes:
                if j not in jours_final:
                    jours_final.append(j)
                if len(jours_final) == nb:
                    break

        # 3) Quota (et gestion groupe par défaut "Autres")
        groupe = cf.get("Groupe", [])
        if not groupe and TAB_GROUPES:
            default_group = TAB_GROUPES.find("Nom du groupe", "Autres")
            if default_group:
                TAB_COUR.update(record_id, {"Groupe": [default_group["id"]]})
                log_event(record_id, "groupe_assigned", payload={"groupe": "Autres"})
        ok_quota, refusal = check_quota(coureur)
        if not ok_quota:
            log_event(record_id, "quota_refused", level="warning", payload=refusal)
            return jsonify(refusal), 429

        # Inputs coureur usuels
        mode = (fget(cf, F_MODE, DEFAULT_MODE) or DEFAULT_MODE).strip()
        objectif_raw = fget(cf, F_OBJECTIF)
        objectif = objectif_raw[0] if isinstance(objectif_raw, list) and objectif_raw else objectif_raw
        objectif = (objectif or "").strip()
        niveau = (fget(cf, F_NIVEAU) or "").strip()

        # 5) Calcul durée plan
        if date_debut_plan and date_fin_plan and date_fin_plan >= date_debut_plan:
            delta = (date_fin_plan - date_debut_plan).days
            nb_semaines = max(1, delta // 7)
            start_date = date_debut_plan
        else:
            if not date_course:
                date_course = (datetime.utcnow() + timedelta(days=30)).date()
            if nb_semaines_input is not None:
                nb_semaines = to_int(nb_semaines_input, DEFAULT_WEEKS)
            else:
                delta_days = max(0, (date_course - date.today()).days)
                nb_semaines = max(1, delta_days // 7)
                if nb_semaines < 4: nb_semaines = 4
                if nb_semaines > 24: nb_semaines = 24
            start_date = (date_course - timedelta(weeks=nb_semaines))
        nb_semaines = max(1, nb_semaines)

        # Jours par semaine
        if jours_par_semaine_input is not None:
            jours_par_semaine = to_int(jours_par_semaine_input, DEFAULT_JOURS_SEMAINE)
        else:
            jours_par_semaine = max(1, min(6, nb))  # ← utilise nb (et plus nb_jours_dispo)

        # 6) Archivage version précédente
        current_version = to_int(cf.get("Version plan"), 0)
        try:
            archived = move_previous_version_to_archives(record_id, current_version)
            log_event(record_id, "archived_previous_version", payload={"count": archived, "version": current_version})
        except Exception as e:
            return jsonify({
                "status": "error",
                "error": "archive_failed",
                "message_id": "SC_COACH_041",
                "message": f"⛔️ Archivage impossible: {str(e)}"
            }), 500

        # 7) Grille S × JOURS_FINAL
        phases = fetch_param_phases() or [
            {"Nom phase": "Base1", "Ordre": 1, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Base2", "Ordre": 2, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Prépa spécifique", "Ordre": 3, "Nb séances max / semaine": jours_par_semaine},
            {"Nom phase": "Course", "Ordre": 4, "Nb séances max / semaine": jours_par_semaine},
        ]

        offsets = [DAY_ORDER.index(j) for j in jours_final] if jours_final else [DAY_ORDER.index(j) for j in (jours_proposes or ["Mercredi","Samedi"])]

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

        # 8) Sélection des séances types
        def candidates_with_fallback(phase_for_pick: str, niv: str) -> List[Dict[str, Any]]:
            cands = filter_types(phase_for_pick, mode, objectif, niv)
            if cands: return cands
            lower = {"Elite":"Avancé","Avancé":"Intermédiaire","Intermédiaire":"Débutant","Débutant":"Reprise","Reprise":None}.get(niv)
            return filter_types(phase_for_pick, mode, objectif, lower) if lower else []

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
                phase_for_pick = "Base1" if (str(phase).lower() in ("prépa générale","prepa generale","base") and (w % 2 == 0)) else ("Base2" if str(phase).lower() in ("prépa générale","prepa generale","base") else phase)
                cands = candidates_with_fallback(phase_for_pick, niveau)
                if not cands:
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
                    "Message coach": st.get("Message coach"),
                    "Message hebdo": st.get("Message hebdo"),
                })

        if date_course and week_buckets.get(nb_semaines - 1):
            ensure_race_and_veille_in_last_week(
                semaine_seances=week_buckets[nb_semaines - 1],
                date_course=date_course,
                mode=mode,
                niveau=niveau,
                objectif=objectif
            )

        # 9) Insertion + rollback
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
                    created_ids.append(created_rec["id"])
                    if len(preview) < 50:
                        preview.append(fields_new.copy())
        except Exception as e:
            for rid in created_ids:
                try: TAB_SEANCES.delete(rid)
                except Exception: pass
            log_event(record_id, "create_failed_rollback", level="error", payload={"error": str(e), "created": created})
            return jsonify({
                "status": "error",
                "error": "create_failed",
                "message_id": "SC_COACH_071",
                "message": f"⛔️ Erreur lors de la création des séances — rollback effectué ({created} items supprimés)."
            }), 500

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
