# -*- coding: utf-8 -*-
"""
SmartCoach API — main.py
Stabilisé (quota + phases + veille/race + messages + logs)
Date: 2025-11-10

Fonctionnalités clés:
- Contrôle QUOTA (SC_COACH_031) via Version plan vs Quota mensuel (et/ou Groupe)
- Génération plan: semaines & jours par semaine configurables (par défaut 10 sem, 2 j/sem.)
- Injection Message coach / hebdo depuis 📘 Séances types
- Placement automatique VEILLE (J-1) & RACE (J) via 📘 Séances types:
  Mode + Phase=Course + Niveau + Objectif, filtré par Clé séance contenant "VEILLE" / "RACE"
- Conservation du nombre de séances en semaine de course (remplacements, pas d’ajout)
- Archivage doux des anciennes séances (si champ "Archive" existe)
- Incrément Version plan uniquement si création effective
- Logs (🧱 Logs SmartCoach) optionnels et silencieux si table absente

Hypothèses:
- Tables: 👤 Coureurs, 🏋️ Séances, 📘 Séances types, ⚙️ Paramètres phases, 🗂️ Messages SmartCoach (optionnelle), 🧱 Logs SmartCoach (optionnelle), 👥 Groupes (optionnelle)
- Champs tolérés par variantes (ex: Objectif / Objectif (normalisé) / Objectif_normalisé)
"""

import os
import json
import traceback
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

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

# Noms de tables
T_COUR = "👤 Coureurs"
T_SEANCES = "🏋️ Séances"
T_TYPES = "📘 Séances types"
T_PARAM = "⚙️ Paramètres phases"
T_MSGS = "🗂️ Messages SmartCoach"     # optionnelle
T_LOGS = "🧱 Logs SmartCoach"         # optionnelle
T_GROUPES = "👥 Groupes"              # optionnelle

# Tables
TAB_COUR = api.table(BASE_ID, T_COUR)
TAB_SEANCES = api.table(BASE_ID, T_SEANCES)
TAB_TYPES = api.table(BASE_ID, T_TYPES)
TAB_PARAM = api.table(BASE_ID, T_PARAM)

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

# Constantes
DEFAULT_WEEKS = 10
DEFAULT_JOURS_SEMAINE = 2
DEFAULT_MODE = "Running"
MESSAGE_ID_QUOTA = "SC_COACH_031"

# Flex: noms de champs possibles côté Coureurs
F_DATE_COURSE = ["date_course", "Date course", "Date objectif", "Jour de course"]
F_OBJECTIF = ["Objectif", "Objectif (normalisé)", "Objectif_normalisé", "Type objectif normalisé"]
F_NIVEAU = ["Niveau", "Niveau (normalisé)", "Niveau_normalisé", "Niveau coach"]
F_MODE = ["Mode", "Mode (normalisé)"]

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

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
        pass  # jamais bloquant

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

def parse_iso_date(v) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, date):
        return datetime.combine(v, datetime.min.time())
    s = str(v)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    return None

def weekday_fr(d: date) -> str:
    names = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    return names[d.weekday()]

def all_records(table) -> List[Dict[str, Any]]:
    try:
        return table.all()
    except Exception:
        return []

def check_quota(coureur: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    f = coureur.get("fields", {})
    version = to_int(f.get("Version plan"), 0)
    quota = to_int(f.get("Quota mensuel"), 0)

    # Surcharge/ajout via Groupe (optionnel)
    try:
        if TAB_GROUPES and f.get("Groupe"):
            # si lié, prend le 1er groupe
            if isinstance(f["Groupe"], list) and f["Groupe"]:
                gid = f["Groupe"][0]
                g = api.table(BASE_ID, T_GROUPES).get(gid)
                gf = g.get("fields", {})
                quota_groupe = to_int(gf.get("Quota mensuel"), 0)
                if quota_groupe > 0:
                    quota = quota_groupe  # override si groupe défini
                # On peut aussi respecter un bool "Autoriser génération"
                autorise = gf.get("Autoriser génération")
                if isinstance(autorise, bool) and not autorise:
                    return False, {
                        "status": "error",
                        "error": "quota_exceeded",
                        "message_id": MESSAGE_ID_QUOTA,
                        "message": "⛔️ Génération interdite par le groupe.",
                        "version_plan": version,
                        "quota_mensuel": quota
                    }
    except Exception:
        pass

    if quota <= 0 or version >= quota:
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
    """Filtrage côté client: Mode + Phase (+ Objectif/niveau si présents)."""
    out = []
    for r in all_records(TAB_TYPES):
        f = r.get("fields", {})
        f_mode = f.get("Mode") or DEFAULT_MODE
        f_phase = f.get("Phase") or f.get("Nom phase")
        if not f_phase:
            continue
        if str(f_mode).lower() != str(mode).lower():
            continue
        if str(f_phase).lower() != str(phase).lower():
            continue

        # Objectif (peut être champ simple ou liste)
        if objectif:
            f_obj = f.get("Objectif") or f.get("Objectifs compatibles")
            if f_obj:
                if isinstance(f_obj, list):
                    if not any(str(objectif).lower() == str(x).lower() for x in f_obj):
                        continue
                else:
                    if str(objectif).lower() not in str(f_obj).lower():
                        continue

        # Niveau (tolérant)
        if niveau:
            f_niv = f.get("Niveau") or f.get("Niveaux compat.") or f.get("Niveau (plage)")
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
    record_id: str,
    semaine_dates: List[date],
    semaine_seances: List[Dict[str, Any]],
    date_course: date,
    mode: str,
    niveau: Optional[str],
    objectif: Optional[str]
):
    """
    Garantit:
    - Une séance le jour de course (= RACE) → remplace séance du jour, sinon déplace la séance la plus proche.
    - La veille J-1 (= VEILLE) → remplace la dernière séance avant J.
    Conserve le nombre de séances.
    """
    # Indexer par date
    by_date = { s["Date"]: s for s in semaine_seances }

    # 1) RACE (J)
    race_day = date_course
    # Trouver un modèle "RACE"
    cands_course = filter_types("Course", mode, objectif, niveau)
    race_cands = [c for c in cands_course if c.get("Clé séance") and "RACE" in str(c["Clé séance"]).upper()]
    race_model = race_cands[0] if race_cands else None

    # S'il n'y a pas de séance à J → déplacer la séance la plus proche vers J
    if race_day not in by_date:
        # choisir la séance la plus proche en absolu
        if semaine_seances:
            semaine_seances.sort(key=lambda s: abs((s["Date"] - race_day).days))
            moved = semaine_seances[0]
            # libérer son ancienne date
            old_date = moved["Date"]
            by_date.pop(old_date, None)
            # la déplacer au jour J
            moved["Date"] = race_day
            by_date[race_day] = moved

    # maintenant on a forcément une séance au jour J
    race_slot = by_date[race_day]
    if race_model:
        # remplacer le contenu par le modèle RACE (conserve date / semaine / jour)
        race_slot.update({
            "Clé séance": race_model["Clé séance"],
            "Nom séance": race_model["Nom séance"] or "Séance",
            "Durée (min)": race_model["Durée (min)"],
            "Charge": race_model["Charge"],
            "Type séance (court)": race_model.get("Type séance (court)"),
            "Message coach": race_model.get("Message coach"),
            "Message hebdo": race_model.get("Message hebdo"),
        })

    # 2) VEILLE (J-1) → dernière séance avant J
    veille_day = race_day - timedelta(days=1)
    # modèle VEILLE
    veille_cands = [c for c in cands_course if c.get("Clé séance") and "VEILLE" in str(c["Clé séance"]).upper()]
    veille_model = veille_cands[0] if veille_cands else None

    # identifier toutes les séances < J et prendre la plus tardive
    pre = [s for s in semaine_seances if s["Date"] < race_day]
    pre.sort(key=lambda s: s["Date"], reverse=True)
    if pre:
        veille_slot = pre[0]  # dernière avant J
        # déplacer au besoin vers J-1
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
            })
    # si pas de séance avant J (cas extrême) → on remplace la plus proche < J ou > J
    else:
        all_sorted = sorted(semaine_seances, key=lambda s: s["Date"])
        if all_sorted:
            candidate = all_sorted[0]
            candidate["Date"] = veille_day
            if veille_model:
                candidate.update({
                    "Clé séance": veille_model["Clé séance"],
                    "Nom séance": veille_model["Nom séance"] or "Séance",
                    "Durée (min)": veille_model["Durée (min)"],
                    "Charge": veille_model["Charge"],
                    "Type séance (court)": veille_model.get("Type séance (court)"),
                    "Message coach": veille_model.get("Message coach"),
                    "Message hebdo": veille_model.get("Message hebdo"),
                })

def create_seance(fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return TAB_SEANCES.create(fields)
    except Exception as e:
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
        nb_semaines = to_int(body.get("nb_semaines"), DEFAULT_WEEKS)
        jours_par_semaine = to_int(body.get("jours_par_semaine"), DEFAULT_JOURS_SEMAINE)

        if not record_id:
            return jsonify({"error": "record_id manquant"}), 400

        # Coureur
        cour = TAB_COUR.get(record_id)
        if not cour or "fields" not in cour:
            return jsonify({"error": "Coureur introuvable"}), 404
        cf = cour["fields"]

        # --- Normalisation du champ "Quota mensuel" (Lookup → nombre) ---
        quota_raw = cf.get("Quota mensuel")

        # Convert lookup list → number
        if isinstance(quota_raw, list):
            quota_mensuel = quota_raw[0] if quota_raw else None
        else:
            quota_mensuel = quota_raw

        # Valeur par défaut si champ vide
        if quota_mensuel is None or quota_mensuel == "":
            quota_mensuel = 999

        # Réinjection dans les données du coureur (pour que check_quota le lise correctement)
        cf["Quota mensuel"] = quota_mensuel

        # --- Vérification du quota ---
        ok, refusal = check_quota(cour)
        if not ok:
            log_event(record_id, "quota_refused", level="warning", payload=refusal)
            return jsonify(refusal), 429

        # Inputs
        mode = fget(cf, F_MODE, DEFAULT_MODE) or DEFAULT_MODE
        objectif = fget(cf, F_OBJECTIF, "10K")
        niveau = fget(cf, F_NIVEAU, "Reprise")

        d_course_dt = parse_iso_date(fget(cf, F_DATE_COURSE))
        if not d_course_dt:
            # fallback neutre : course dans 30j (pour éviter crash, mais RG: normalement renseigné)
            d_course_dt = (datetime.utcnow() + timedelta(days=30))
        date_course = d_course_dt.date()

        # Paramètres phases (ordre)
        phases = fetch_param_phases()
        if not phases:
            # fallback neutre s'il n'y a rien
            phases = [
                {"Nom phase": "Base1", "Ordre": 1, "Nb séances max / semaine": jours_par_semaine},
                {"Nom phase": "Base2", "Ordre": 2, "Nb séances max / semaine": jours_par_semaine},
                {"Nom phase": "Prépa spécifique", "Ordre": 3, "Nb séances max / semaine": jours_par_semaine},
                {"Nom phase": "Course", "Ordre": 4, "Nb séances max / semaine": jours_par_semaine},
            ]

        # ARCHIVE
        archives = archive_existing_sessions(record_id)

        # Calendrier: on prend nb_semaines avant la date de course
        start_date = (date_course - timedelta(weeks=nb_semaines))
        # offsets par défaut (ven, dim)
        if jours_par_semaine <= 0:
            jours_par_semaine = DEFAULT_JOURS_SEMAINE
        if jours_par_semaine == 1:
            offsets = [6]          # dimanche
        elif jours_par_semaine == 2:
            offsets = [4, 6]       # vendredi, dimanche
        elif jours_par_semaine == 3:
            offsets = [2, 4, 6]    # mercredi, vendredi, dimanche
        else:
            offsets = [1, 3, 4, 6][:jours_par_semaine]  # mar/jeu/ven/dim (tronqué)

        # Répartition des phases sur nb_semaines (réparti égal sur toutes sauf "Course" qu'on force à 1)
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
            # ne pas dépasser base_weeks
            if cursor + count > base_weeks:
                count = max(1, base_weeks - cursor)
            for _ in range(count):
                phase_timeline.append(name)
            cursor += count
        # force dernière semaine à Course
        while len(phase_timeline) < nb_semaines - 1:
            phase_timeline.append(non_course[-1] if non_course else "Base2")
        phase_timeline.append("Course")
        phase_timeline = phase_timeline[:nb_semaines]

        # Génération "mémoire" (avant écriture Airtable)
        created = 0
        preview: List[Dict[str, Any]] = []

        # Générer toutes les semaines
        week_buckets: Dict[int, List[Dict[str, Any]]] = {}  # semaine idx -> séances (avant écriture)
        for w in range(nb_semaines):
            week_buckets[w] = []
            monday = start_date + timedelta(weeks=w)
            for j_index, off in enumerate(offsets[:jours_par_semaine]):
                d = (monday + timedelta(days=off)).date()
                phase = phase_timeline[w]

                # Sélection standard
                phase_for_pick = phase
                if str(phase).lower() in ("prépa générale", "prepa generale", "base"):
                    # alternance simple si tu utilises Base1/Base2
                    phase_for_pick = "Base1" if (w % 2 == 0) else "Base2"

                cands = filter_types(phase_for_pick, mode, objectif, niveau)
                st = pick_deterministic(cands, w, j_index)
                # structure mémoire (sans envoi encore)
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

        # Ajustement semaine de course pour VEILLE & RACE
        last_w = nb_semaines - 1
        if week_buckets.get(last_w):
            # garantir RACE/VEILLE
            ensure_race_and_veille_in_last_week(
                record_id=record_id,
                semaine_dates=[s["Date"] for s in week_buckets[last_w]],
                semaine_seances=week_buckets[last_w],
                date_course=date_course,
                mode=mode,
                niveau=niveau,
                objectif=objectif
            )

        # Écriture Airtable
        version_next = to_int(cf.get("Version plan"), 0) + 1
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
                created_rec = create_seance(fields_new)
                if created_rec:
                    created += 1
                    if len(preview) < 40:
                        pr = fields_new.copy()
                        preview.append(pr)

        # Incrément Version plan si création
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
            "archives": archives,
            "preview": preview
        }), 200

    except Exception as e:
        rid = None
        try:
            rid = (request.get_json() or {}).get("record_id")
        except Exception:
            pass
        log_event(rid or "unknown", "generation_failed", level="error",
                  payload={"error": str(e), "trace": traceback.format_exc()})
        return jsonify({"status": "error", "error": "internal_error", "message": str(e)}), 500


if __name__ == "__main__":
    # Port Render par défaut, debug activé pour trace locale
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=True)
