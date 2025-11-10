# -*- coding: utf-8 -*-
"""
SmartCoach API — main.py
Version: 2025-11-10 (stable)

Fonctionnalités:
- Contrôle de quota (SC_COACH_031) avec normalisation Lookup -> number
- Phases via ⚙️ Paramètres phases, dernière semaine forcée "Course"
- Séances via 📘 Séances types (Mode + Phase + Niveau + Objectif)
- Placement automatique VEILLE (J-1) & RACE (Jour J) en semaine de course
- Archivage doux; incrément Version plan si création
- Logs optionnels 🧱 Logs SmartCoach
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

# Noms des tables (ajuste si besoin)
T_COUR = "👤 Coureurs"
T_SEANCES = "🏋️ Séances"
T_TYPES = "📘 Séances types"
T_PARAM = "⚙️ Paramètres phases"
T_MSGS = "🗂️ Messages SmartCoach"     # optionnelle
T_LOGS = "🧱 Logs SmartCoach"         # optionnelle
T_GROUPES = "👥 Groupes"              # optionnelle

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
F_JOURS_DISPO = ["Jours disponibles", "jours_disponibles", "Disponibilités"]

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
    """Retourne un objet date (ou None). Accepte date, datetime, str (YYYY-MM-DD)."""
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    s = str(x).strip()
    # Formats courants Airtable
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    # Tentative ISO
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
    """Airtable Lookup -> retourne le 1er nombre; gère aussi number direct ou ''."""
    if isinstance(v, list):
        if not v:
            return default
        return to_int(v[0], default if default is not None else 0)
    if v in (None, ""):
        return default
    return to_int(v, default if default is not None else 0)

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

    # Si quota non défini → ne pas bloquer
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

def fetch_param_phases() -> List[Dict[str, Any]]:
    """Retourne les phases triées par Ordre."""
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
    """
    Filtrage côté client sur 📘 Séances types:
    - obligatoire: Mode + Phase
    - optionnel: Objectif, Niveau (tolérance: champ simple ou liste)
    """
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

        # Objectif
        if objectif:
            f_obj = f.get("Objectif") or f.get("Objectifs compatibles")
            if f_obj:
                if isinstance(f_obj, list):
                    if not any(str(objectif).lower() == str(x).lower() for x in f_obj):
                        continue
                else:
                    if str(objectif).lower() not in str(f_obj).lower():
                        continue

        # Niveau
        if niveau:
            f_niv = f.get("Niveau") or f.get("Niveaux compat.") or f.get("Niveau (plage)") or f.get("Niveaux compatibles")
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

def archive_existing_sessions(record_id: str) -> int:
    """Marque Archive=True si le champ existe (ne supprime pas)."""
    count = 0
    try:
        recs = TAB_SEANCES.all(formula=f"FIND('{record_id}', ARRAYJOIN({{Coureur}}))")
        for r in recs:
            f = r.get("fields", {})
            if "Archive" in f and not f.get("Archive"):
                TAB_SEANCES.update(r["id"], {"Archive": True})
                count += 1
    except Exception:
        pass
    return count

def ensure_race_and_veille_in_last_week(
    semaine_seances: List[Dict[str, Any]],
    date_course: date,
    mode: str,
    niveau: Optional[str],
    objectif: Optional[str]
):
    """
    Garantit en semaine de course:
    - Une séance le jour J = RACE (remplacement du contenu par modèle 'RACE')
    - Une séance la veille J-1 = VEILLE (remplacement du contenu par modèle 'VEILLE')
    - Conserve le nombre de séances (déplace/remplace, pas d'ajout)
    """
    if not semaine_seances:
        return

    # Index rapide par date
    by_date = { s["Date"]: s for s in semaine_seances }

    # Charger modèles Phase=Course
    cands_course = filter_types("Course", mode, objectif, niveau)
    race_model = next((c for c in cands_course if c.get("Clé séance") and "RACE" in str(c["Clé séance"]).upper()), None)
    veille_model = next((c for c in cands_course if c.get("Clé séance") and "VEILLE" in str(c["Clé séance"]).upper()), None)

    # --- RACE (Jour J) ---
    race_day = date_course
    if race_day not in by_date:
        # Déplacer la séance la plus proche vers J
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

    # --- VEILLE (J-1) ---
    veille_day = race_day - timedelta(days=1)
    # dernière séance avant J
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
        # cas extrême: pas de séance avant J → prend la première et place à J-1
        all_sorted = sorted(semaine_seances, key=lambda s: s["Date"])
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

def create_seance(fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return TAB_SEANCES.create(fields)
    except Exception:
        return None

# -----------------------------------------------------------------------------
# FLASK APP
# -----------------------------------------------------------------------------

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def health():
    return "SmartCoach API up", 200

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    try:
        body = request.get_json(force=True, silent=True) or {}
        record_id = body.get("record_id")

        # facultatifs (si non fournis -> calculs automatiques)
        nb_semaines_input = body.get("nb_semaines")
        jours_par_semaine_input = body.get("jours_par_semaine")

        if not record_id:
            return jsonify({"error": "record_id manquant"}), 400

        # Coureur
        coureur = TAB_COUR.get(record_id)
        if not coureur or "fields" not in coureur:
            return jsonify({"error": "Coureur introuvable"}), 404
        cf = coureur["fields"]

        # Normaliser Quota mensuel (Lookup -> number)
        quota_raw = cf.get("Quota mensuel")
        quota_mensuel = normalize_lookup_number(quota_raw, None)
        if quota_mensuel is None:
            quota_mensuel = 999  # pas de blocage si non défini
        cf["Quota mensuel"] = quota_mensuel

        # Vérification Quota
        ok, refusal = check_quota(coureur)
        if not ok:
            log_event(record_id, "quota_refused", level="warning", payload=refusal)
            return jsonify(refusal), 429

        # Inputs coureur
        mode = fget(cf, F_MODE, DEFAULT_MODE) or DEFAULT_MODE
        objectif = fget(cf, F_OBJECTIF, "10K")
        niveau = fget(cf, F_NIVEAU, "Reprise")
        date_obj = normalize_date(fget(cf, F_DATE_COURSE))
        if not date_obj:
            # fallback: course dans 30 jours
            date_obj = (datetime.utcnow() + timedelta(days=30)).date()

        # nb semaines
        if nb_semaines_input is not None:
            nb_semaines = to_int(nb_semaines_input, DEFAULT_WEEKS)
        else:
            # Calcul automatique (RG: durée plan)
            delta_days = max(0, (date_obj - date.today()).days)
            nb_semaines = max(1, delta_days // 7)
            if nb_semaines < 4:
                nb_semaines = 4
            if nb_semaines > 24:
                nb_semaines = 24

        # jours par semaine
        if jours_par_semaine_input is not None:
            jours_par_semaine = to_int(jours_par_semaine_input, DEFAULT_JOURS_SEMAINE)
        else:
            # Essai à partir des champs "Jours disponibles" si présent
            jdispo = fget(cf, F_JOURS_DISPO)
            if isinstance(jdispo, list):
                jours_par_semaine = max(1, min(6, len(jdispo)))
            else:
                # fallback
                jours_par_semaine = DEFAULT_JOURS_SEMAINE

        # Phases
        phases = fetch_param_phases()
        if not phases:
            phases = [
                {"Nom phase": "Base1", "Ordre": 1, "Nb séances max / semaine": jours_par_semaine},
                {"Nom phase": "Base2", "Ordre": 2, "Nb séances max / semaine": jours_par_semaine},
                {"Nom phase": "Prépa spécifique", "Ordre": 3, "Nb séances max / semaine": jours_par_semaine},
                {"Nom phase": "Course", "Ordre": 4, "Nb séances max / semaine": jours_par_semaine},
            ]

        # Archivage des séances existantes
        archives = archive_existing_sessions(record_id)

        # Construction calendrier
        start_date = (date_obj - timedelta(weeks=nb_semaines))
        if jours_par_semaine <= 0:
            jours_par_semaine = DEFAULT_JOURS_SEMAINE
        # offsets par défaut (mar/jeu/ven/dim selon besoin)
        if jours_par_semaine == 1:
            offsets = [6]                  # Dim
        elif jours_par_semaine == 2:
            offsets = [4, 6]               # Ven, Dim
        elif jours_par_semaine == 3:
            offsets = [2, 4, 6]            # Mer, Ven, Dim
        elif jours_par_semaine == 4:
            offsets = [1, 3, 4, 6]         # Mar, Jeu, Ven, Dim
        else:
            offsets = [1, 2, 3, 4, 6][:jours_par_semaine]  # Mar, Mer, Jeu, Ven, Dim (tronqué)

        # Timeline des phases: dernière semaine = Course
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

        created = 0
        preview: List[Dict[str, Any]] = []
        version_next = to_int(cf.get("Version plan"), 0) + 1

        # Génération en mémoire
        week_buckets: Dict[int, List[Dict[str, Any]]] = {}
        for w in range(nb_semaines):
            week_buckets[w] = []
            monday = start_date + timedelta(weeks=w)
            phase = phase_timeline[w]

            for j_index, off in enumerate(offsets[:jours_par_semaine]):
                d = (monday + timedelta(days=off)).date()
                phase_for_pick = phase
                if str(phase).lower() in ("prépa générale", "prepa generale", "base"):
                    phase_for_pick = "Base1" if (w % 2 == 0) else "Base2"

                cands = filter_types(phase_for_pick, mode, objectif, niveau)
                st = pick_deterministic(cands, w, j_index)

                if st:
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
                else:
                    log_event(record_id, "no_type_found", level="warning",
                              payload={"phase": phase_for_pick, "week": w+1, "date": str(d), "mode": mode, "objectif": objectif, "niveau": niveau})

        # Ajustement semaine Course: VEILLE (J-1) et RACE (J)
        last_w = nb_semaines - 1
        if week_buckets.get(last_w):
            ensure_race_and_veille_in_last_week(
                semaine_seances=week_buckets[last_w],
                date_course=date_obj,
                mode=mode,
                niveau=niveau,
                objectif=objectif
            )

        # Écriture Airtable
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
                if create_seance(fields_new):
                    created += 1
                    if len(preview) < 50:
                        preview.append(fields_new.copy())

        # Incrément Version plan si création effective
        if created > 0:
            old_v = to_int(cf.get("Version plan"), 0)
            try:
                TAB_COUR.update(record_id, {"Version plan": old_v + 1})
                log_event(record_id, "version_plan_incremented", payload={"from": old_v, "to": old_v + 1})
            except Exception as e:
                log_event(record_id, "version_plan_increment_failed", level="error",
                          payload={"error": str(e), "from": old_v})

        msg = f"✅ Nouveau plan généré — **Version {version_next}**\n{created} séances créées."
        return jsonify({
            "status": "ok",
            "message_id": "SC_COACH_021",
            "message": msg,
            "nb_semaines": nb_semaines,
            "jours_par_semaine": jours_par_semaine,
            "version_plan": version_next,
            "total": created,
            "archives": archive_existing_sessions.__name__,  # info: fonction utilisée (pas le nb)
            "preview": preview
        }), 200

    except Exception as e:
        rid = None
        try:
            rid = (request.get_json(silent=True) or {}).get("record_id")
        except Exception:
            pass
        log_event(rid or "unknown", "generation_failed", level="error",
                  payload={"error": str(e), "trace": traceback.format_exc()})
        return jsonify({"status": "error", "error": "internal_error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=True)