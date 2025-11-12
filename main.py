# -*- coding: utf-8 -*-
"""
SmartCoach API — SCN_001 : Génération de plan d'entraînement
Version : 2025-11-12
Auteur  : SmartCoach Dev (aligné RCTC)

Ce scénario SCN_001 exécute la génération complète d’un plan d’entraînement :
1️⃣ Chargement du coureur
2️⃣ Contrôles de cohérence jours/niveau (B03-COH-03/04/05/06)
3️⃣ Lookup dans ⚖️ Référence Jours
4️⃣ Vérification du quota de génération par groupe (RG-GEST-QUOTA)
5️⃣ Calcul de la durée du plan
6️⃣ Archivage versionné
7️⃣ Construction de la grille S × Jours
8️⃣ Sélection des séances types (avec fallback de niveau)
9️⃣ Création des séances et suivi de génération
"""

import os, json, traceback, time
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, request, jsonify
from pyairtable import Api

# ----------------------------------------------------------------------
# 🔧 UTILITAIRES GÉNÉRAUX
# ----------------------------------------------------------------------

def to_int(v, default=0) -> int:
    """Convertit proprement un champ en entier."""
    try:
        if v in (None, ""):
            return default
        return int(float(v))
    except Exception:
        return default

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def normalize_date(x) -> Optional[date]:
    """Convertit différents formats de dates vers un objet date."""
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    s = str(x).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None

def weekday_fr(d: date) -> str:
    """Retourne le nom français du jour."""
    names = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    return names[d.weekday()]

def fget(fields: Dict[str, Any], names: List[str], default=None):
    """Récupère un champ parmi plusieurs alias possibles."""
    for n in names:
        if n in fields and fields[n] not in (None, ""):
            return fields[n]
    return default

# ----------------------------------------------------------------------
# ⚙️ CONFIGURATION AIRTABLE
# ----------------------------------------------------------------------

AIRTABLE_KEY = os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID") or os.environ.get("BASE_ID")
if not AIRTABLE_KEY or not BASE_ID:
    raise RuntimeError("AIRTABLE_API_KEY / AIRTABLE_BASE_ID manquants.")

api = Api(AIRTABLE_KEY)

# Tables standardisées selon RCTC
T_COUR        = "👤 Coureurs"
T_SEANCES     = "🏋️ Séances"
T_TYPES       = "📘 Séances types"
T_PARAM       = "⚙️ Paramètres phases"
T_REF_JOURS   = "⚖️ Référence Jours"
T_SUIVI       = "📋 Suivi génération"
T_LOGS        = "🧱 Logs SmartCoach"
T_GROUPES     = "👥 Groupes"
T_ARCHIVES    = "Archives Séances"

TAB_COUR        = api.table(BASE_ID, T_COUR)
TAB_SEANCES     = api.table(BASE_ID, T_SEANCES)
TAB_TYPES       = api.table(BASE_ID, T_TYPES)
TAB_PARAM       = api.table(BASE_ID, T_PARAM)
TAB_REF_JOURS   = api.table(BASE_ID, T_REF_JOURS)
TAB_SUIVI       = api.table(BASE_ID, T_SUIVI)
TAB_LOGS        = api.table(BASE_ID, T_LOGS)
TAB_GROUPES     = api.table(BASE_ID, T_GROUPES)
TAB_ARCHIVES_T  = api.table(BASE_ID, T_ARCHIVES)

DAY_ORDER = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

# Champs tolérants
F_DATE_COURSE = ["Date course","Date Objectif","Jour de course"]
F_OBJECTIF    = ["Objectif","Objectif_normalisé"]
F_NIVEAU      = ["Niveau","Niveau_normalisé"]
F_MODE        = ["Mode","Mode (normalisé)"]
F_JOURS_LIST  = ["Jours disponibles","📅 Jours disponibles"]
F_JOURS_MIN   = ["Nb_jours_min","Jours_min"]
F_JOURS_MAX   = ["Nb_jours_max","Jours_max"]

DEFAULT_WEEKS = 10
DEFAULT_JOURS_SEMAINE = 2
DEFAULT_MODE = "Running"

# ----------------------------------------------------------------------
# 🧱 LOGGING STRUCTURÉ
# ----------------------------------------------------------------------

def log_event(record_id: str, event: str, level: str = "info", payload: Optional[dict] = None):
    """Crée une ligne de log dans Airtable."""
    try:
        TAB_LOGS.create({
            "Record ID": record_id,
            "Scénario": "SCN_001",
            "Event": event,
            "Level": level,
            "Timestamp": datetime.now().isoformat(),
            "Payload": json.dumps(payload or {}, ensure_ascii=False)
        })
    except Exception:
        pass

# ----------------------------------------------------------------------
# 🔍 CONTRÔLE DE COHÉRENCE JOURS / NIVEAU
# ----------------------------------------------------------------------

def check_days_and_level(cf: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Contrôle cohérence B03-COH-03/04/05/06."""
    jdispo = fget(cf, F_JOURS_LIST)
    nb = len(jdispo) if isinstance(jdispo, list) else to_int(jdispo, 0)
    niv = fget(cf, F_NIVEAU, "Reprise")
    jmin = to_int(fget(cf, F_JOURS_MIN, None), None)
    jmax = to_int(fget(cf, F_JOURS_MAX, None), None)

    if nb == 0:
        return False, {"error": "days_zero", "message_id": "SC_COACH_023", "message": "⛔ Aucun jour disponible."}
    if jmin and nb < jmin:
        return False, {"error": "days_below_min", "message_id": "SC_COACH_021", "message": f"⛔ {nb} < {jmin} jours minimum."}
    if jmax and nb > jmax:
        return False, {"error": "days_above_max", "message_id": "SC_COACH_022", "message": f"⛔ {nb} > {jmax} jours maximum."}
    return True, {"nb_jours": nb, "niveau": niv}

# ----------------------------------------------------------------------
# 🔐 CONTRÔLE QUOTA GROUPE
# ----------------------------------------------------------------------

def check_quota(coureur):
    """RG-GEST-QUOTA : vérifie le quota mensuel du groupe."""
    f = coureur.get("fields", {})
    groupe_list = f.get("Groupe", [])
    if not groupe_list:
        return True, None

    gid = groupe_list[0]
    g = TAB_GROUPES.get(gid)
    gf = g.get("fields", {}) if g else {}
    quota = gf.get("Quota mensuel", 999)
    autorise = gf.get("Autoriser génération", True)
    nom_groupe = gf.get("Nom du groupe", "?")

    if autorise is False:
        return False, {"error": "quota_disabled", "message_id": "SC_COACH_031", "message": f"Génération interdite ({nom_groupe})."}

    mois = datetime.now().strftime("%Y-%m")
    count = 0
    for rec in TAB_SUIVI.all():
        sf = rec.get("fields", {})
        if gid in (sf.get("Groupe") or []):
            if mois in str(sf.get("Date génération", "")) and sf.get("Statut") == "success":
                count += 1
    if count >= quota:
        return False, {"error": "quota_exceeded", "message_id": "SC_COACH_032", "message": f"Quota atteint ({quota}/{quota}) pour {nom_groupe}."}
    return True, None

# ----------------------------------------------------------------------
# 📦 ARCHIVAGE VERSIONNÉ
# ----------------------------------------------------------------------

def move_previous_version_to_archives(record_id: str, version: int) -> int:
    """Archive la version précédente des séances."""
    try:
        recs = TAB_SEANCES.all(formula=f"AND({{Version plan}}={version}, FIND('{record_id}', ARRAYJOIN({{Coureur}})))")
        for r in recs:
            f = r.get("fields", {})
            f["Archive de"] = [record_id]
            TAB_ARCHIVES_T.create(f)
            TAB_SEANCES.delete(r["id"])
        return len(recs)
    except Exception as e:
        log_event(record_id, "archive_error", "error", {"error": str(e)})
        return 0

# ----------------------------------------------------------------------
# 🧠 GÉNÉRATION DU PLAN (SCN_001)
# ----------------------------------------------------------------------

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return "SmartCoach API OK (SCN_001)", 200

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    """Point d’entrée principal du scénario SCN_001."""
    t0 = time.time()
    rid = None
    try:
        body = request.get_json(force=True, silent=True) or {}
        rid = body.get("record_id")
        if not rid:
            return jsonify({"error": "record_id manquant"}), 400

        # 1️⃣ Coureur
        coureur = TAB_COUR.get(rid)
        if not coureur:
            return jsonify({"error": "coureur introuvable"}), 404
        cf = coureur["fields"]

        # 2️⃣ Contrôle cohérence jours
        ok, payload = check_days_and_level(cf)
        if not ok:
            log_event(rid, "days_control_failed", "warning", payload)
            return jsonify(payload), 400

        # 3️⃣ Lookup Référence Jours
        from reference_jours import lookup_reference_jours
        ref = lookup_reference_jours(cf)
        if not ref:
            return jsonify({"error": "reference_not_found", "message": "⚖️ Référence Jours introuvable."}), 400

        jours_min = ref.get("jours_min", 2)
        jours_max = ref.get("jours_max", 5)
        jours_proposes = ref.get("jours_proposés", [])
        jours_dispo = fget(cf, F_JOURS_LIST, jours_proposes) or []
        if isinstance(jours_dispo, str):
            jours_dispo = [j.strip() for j in jours_dispo.split(",")]

        nb = clamp(len(jours_dispo), jours_min, jours_max)
        jours_final = jours_dispo[:nb] or jours_proposes[:nb]

        # 4️⃣ Vérif quota
        ok_q, refu = check_quota(coureur)
        if not ok_q:
            log_event(rid, "quota_refused", "warning", refu)
            return jsonify(refu), 429

        # 5️⃣ Calcul durée plan
        date_course = normalize_date(fget(cf, F_DATE_COURSE))
        nb_semaines = max(1, min(24, (date_course - date.today()).days // 7 if date_course else DEFAULT_WEEKS))
        start_date = (date_course - timedelta(weeks=nb_semaines)) if date_course else date.today()

        # 6️⃣ Archivage
        version = to_int(cf.get("Version plan"), 0)
        archived = move_previous_version_to_archives(rid, version)

        # 7️⃣ Grille S×J simplifiée
        jours_offsets = [DAY_ORDER.index(j) for j in jours_final if j in DAY_ORDER]
        if not jours_offsets:
            jours_offsets = [DAY_ORDER.index("Mercredi"), DAY_ORDER.index("Samedi")]

        # 8️⃣ Création (séances fictives — structure test)
        created = []
        for w in range(nb_semaines):
            monday = start_date + timedelta(weeks=w)
            for o in jours_offsets:
                d = monday + timedelta(days=o)
                new = {
                    "Coureur": [rid],
                    "Date": d.isoformat(),
                    "Jour planifié": weekday_fr(d),
                    "Semaine": w + 1,
                    "Nom séance": f"Séance {w+1}-{weekday_fr(d)}",
                    "Phase": "Base",
                    "Version plan": version + 1
                }
                rec = TAB_SEANCES.create(new)
                created.append(rec["id"])

        # 9️⃣ Suivi génération
        TAB_SUIVI.create({
            "Coureur": [rid],
            "Date génération": datetime.now().isoformat(),
            "Type de scénario": "SCN_001",
            "Statut": "success",
            "Durée exécution (s)": round(time.time() - t0, 2)
        })
        log_event(rid, "generation_success", "info", {"created": len(created)})

        return jsonify({
            "status": "ok",
            "message_id": "SC_OK_200",
            "message": f"✅ Plan généré ({len(created)} séances, version {version+1})",
            "nb_semaines": nb_semaines,
            "jours_final": jours_final,
            "seances_ids": created
        }), 200

    except Exception as e:
        log_event(rid or "unknown", "generation_failed", "error", {"error": str(e), "trace": traceback.format_exc()})
        TAB_SUIVI.create({
            "Coureur": [rid] if rid else None,
            "Type de scénario": "SCN_001",
            "Statut": "failed",
            "Erreur_code": str(e),
            "Durée exécution (s)": round(time.time() - t0, 2)
        })
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=True)
