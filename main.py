import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, date
from dateutil.parser import parse as dtparse
from pyairtable import Table

app = Flask(__name__)

# =============================
# ENV & TABLE HELPERS
# =============================
def getenv_any(*keys, default=None):
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return default

API_KEY = getenv_any("AIRTABLE_API_KEY", "AIRTABLE_KEY")
BASE_ID = getenv_any("AIRTABLE_BASE_ID", "BASE_ID")

def get_table(name_env_key, *fallback_names):
    """Prend d'abord le nom depuis l'ENV, sinon essaye les fallback dans l'ordre."""
    tbl_name = os.environ.get(name_env_key)
    if tbl_name:
        return Table(API_KEY, BASE_ID, tbl_name)
    last_exc = None
    for nm in fallback_names:
        try:
            return Table(API_KEY, BASE_ID, nm)
        except Exception as e:
            last_exc = e
            continue
    # s'il échoue sur tous, re-lève la dernière exception pour debug
    if last_exc:
        raise last_exc
    # ou dernier recours
    return Table(API_KEY, BASE_ID, fallback_names[-1])

TABLE_COUR          = get_table("TABLE_COUR",
                                "👤 Coureurs", "Coureurs")
TABLE_SEANCES       = get_table("TABLE_SEANCES",
                                "🏋️ Séances", "Séances")
TABLE_ARCHIVES      = get_table("TABLE_ARCHIVES",
                                "🗄️ Archives Séances", "🗄️ Archives", "Archives")
TABLE_SEANCES_TYPES = get_table("TABLE_SEANCES_TYPES",
                                "📘 Séances types", "Séances types")
TABLE_STRUCTURE     = get_table("TABLE_STRUCTURE",
                                "📐 Structure Séances", "Structure Séances")
TABLE_MAILS         = get_table("TABLE_MAILS",
                                "📬 Mails", "Mails")

# =============================
# HELPERS
# =============================
JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
JOUR_IDX = {j:i for i,j in enumerate(JOURS_FR)}  # Lundi=0 ... Dimanche=6

def safe(f, k, default=None):
    v = f.get(k)
    return default if v in (None, "", []) else v

def parse_date_iso_or_ddmmyyyy(s) -> date | None:
    if not s:
        return None
    # Try ISO-like first
    try:
        return dtparse(str(s).replace("Z","").replace("z","")).date()
    except Exception:
        pass
    # Try dd/mm/yyyy
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        return None

def to_ddmmyyyy(d: date) -> str:
    return d.strftime("%d/%m/%Y")

def date_for_week_and_weekday(date_debut: date | None, week_index_1based: int, weekday_name: str) -> date:
    """Semaine 1 = semaine glissante à partir de date_debut (sans réaligner au lundi)."""
    if date_debut is None:
        date_debut = datetime.today().date()
    weekday_target = JOUR_IDX.get(weekday_name, 0)
    base = date_debut + timedelta(weeks=(week_index_1based-1))
    offset = (weekday_target - base.weekday()) % 7
    return base + timedelta(days=offset)

def type_court_from_key_or_long(cle, type_long):
    """
    Normalise en code court : EF/SL/SEUIL/VMA/AS10/TECH/ACT/OFF/VEILLE/RECUP.
    """
    src = (cle or type_long or "").upper().strip()
    if src.startswith("EF") or "ENDURANCE" in src or src in ["E","EF"]:
        return "EF"
    if src.startswith("SL") or "SORTIE LONGUE" in src:
        return "SL"
    if src.startswith("SEU") or src.startswith("SEUIL") or src in ["T"]:
        return "SEUIL"
    if src.startswith("VMA") or src in ["I"]:
        return "VMA"
    if src.startswith("AS10") or "ALLURE 10" in src or "ALLURE 10K" in src:
        return "AS10"
    if src.startswith("TECH"):
        return "TECH"
    if src.startswith("ACT"):
        return "ACT"
    if src == "OFF" or "REPOS" in src:
        return "OFF"
    if "VEILLE" in src:
        return "VEILLE"
    if "RELAX" in src or "TRÈS LÉGER" in src or "TRES LEGER" in src or "RECUP" in src:
        return "RECUP"
    return "EF"

def build_ics(date_ddmmyyyy, title, desc):
    d = datetime.strptime(date_ddmmyyyy, "%d/%m/%Y")
    DTSTART = d.strftime("%Y%m%d")
    DTEND = (d + timedelta(days=1)).strftime("%Y%m%d")
    uid = f"{int(datetime.utcnow().timestamp())}-{abs(hash(title+DTSTART))}@smartcoach"
    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SmartCoach//FR",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{DTSTART}",
        f"DTEND;VALUE=DATE:{DTEND}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{desc or ''}",
        "END:VEVENT",
        "END:VCALENDAR"
    ])

def weeks_between(d1: date, d2: date) -> int:
    try:
        return max(1, round((d2 - d1).days / 7))
    except Exception:
        return 8

def verifier_jours(fields) -> int:
    """RG B03-COH : clamp nb jours entre min/max ; fallback = nb jours dispo."""
    jours_dispo = fields.get("📅 Jours_disponibles") or fields.get("Jours_disponibles")
    if isinstance(jours_dispo, list):
        jd = len(jours_dispo)
    else:
        try:
            jd = int(jours_dispo or 0)
        except Exception:
            jd = 0
    try:
        jmin = int(fields.get("Jours_min")) if fields.get("Jours_min") is not None else None
        jmax = int(fields.get("Jours_max")) if fields.get("Jours_max") is not None else None
    except Exception:
        jmin, jmax = None, None
    if jmin is None or jmax is None:
        return max(1, jd or 1)
    return max(jmin, min(jd, jmax))

# =============================
# ARCHIVAGE
# =============================
def archive_records(records, version):
    """
    Archivage physique :
    - copie champs pertinents dans 🗄️ Archives*
    - ajoute méta : ID séance originale, Version plan, Date archivage (UTC), Source
    - supprime la séance active
    """
    count = 0
    for r in records:
        f = r.get("fields", {}).copy()
        archive_payload = {
            # méta
            "ID séance originale": r.get("id"),
            "Version plan": version,
            "Date archivage": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Source": "auto-archive",
            # copie champs si existent
            "Coureur": f.get("Coureur"),
            "Clé séance": f.get("Clé séance"),
            "Nom séance": f.get("Nom séance"),
            "Type séance": f.get("Type séance"),
            "Phase": f.get("Phase"),
            "Durée (min)": f.get("Durée (min)"),
            "Charge": f.get("Charge"),
            "Semaine": f.get("Semaine"),
            "Jour planifié": f.get("Jour planifié"),
            "Jour (nom)": f.get("Jour (nom)"),
            "Date planifiée": f.get("Date planifiée") or f.get("Date"),
            "🧠 Message_coach": f.get("🧠 Message_coach"),
        }
        TABLE_ARCHIVES.create(archive_payload)
        TABLE_SEANCES.delete(r["id"])
        count += 1
    return count

# =============================
# STRUCTURE SÉANCES (pivot)
# =============================
def get_structure(phase, niveau, objectif, frequence):
    # Phase/Niveau/Objectif/Fréquence présents dans 📐 Structure Séances
    formula = (
        "AND("
        f"{{Phase}} = '{phase}',"
        f"{{Niveau}} = '{niveau}',"
        f"{{Objectif}} = '{objectif}',"
        f"{{Fréquence}} = {int(frequence)}"
        ")"
    )
    rows = TABLE_STRUCTURE.all(formula=formula)
    out = {}
    for r in rows:
        f = r.get("fields", {})
        sem = safe(f, "Semaine")
        cle = safe(f, "Clé séance")
        if not sem or not cle:
            continue
        sem = int(sem)
        out.setdefault(sem, []).append(cle)

    # SL en dernier (fin de semaine)
    for k, v in out.items():
        out[k] = sorted(v, key=lambda c: ("SL" in (c or "")))
    return dict(sorted(out.items(), key=lambda x: x[0]))

def assign_days(structure, jours_dispos):
    """
    Mappe les clés à (semaine, jour_nom, ordre_du_jour) :
    - SL sur le dernier jour dispo
    - EF sur le 1er jour dispo
    - le reste se remplit en ordre sur les jours restants
    """
    if not jours_dispos:
        jours_dispos = ["Vendredi","Dimanche"]
    jours = [j for j in jours_dispos if j in JOURS_FR]
    if not jours:
        jours = ["Vendredi","Dimanche"]

    res = []
    for semaine, cles in structure.items():
        # prépare l’ordre hebdo
        days_used = []
        # place SL
        for idx, cle in enumerate(cles):
            if str(cle).upper().startswith("SL") and jours[-1] not in days_used:
                res.append((semaine, jours[-1], idx+1, cle))
                days_used.append(jours[-1])
        # place EF
        for idx, cle in enumerate(cles):
            if str(cle).upper().startswith("EF"):
                # 1er jour libre
                for j in jours:
                    if j not in days_used:
                        res.append((semaine, j, idx+1, cle))
                        days_used.append(j)
                        break
        # place le reste
        for idx, cle in enumerate(cles):
            if str(cle).upper().startswith(("SL","EF")):
                continue
            for j in jours:
                if j not in days_used:
                    res.append((semaine, j, idx+1, cle))
                    days_used.append(j)
                    break
    # trie par semaine puis par ordre calculé (Jour planifié numérique)
    res.sort(key=lambda x: (x[0], x[2]))
    return res  # list of (semaine, jour_nom, ordre, cle)

# =============================
# ROUTES
# =============================
@app.get("/")
def health():
    return "SmartCoach API active ✅"

@app.post("/generate_by_id")
def generate_by_id():
    data = request.json or {}
    record_id = data.get("record_id") or data.get("id")
    if not record_id:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_001",
            "message": "⚠️ Aucun ID de coureur reçu.",
            "expected_format": {"record_id": "recXXXXXXXXXXXXXX"}
        }), 400

    # -- Coureur
    try:
        rec = TABLE_COUR.get(record_id)
    except Exception as e:
        return jsonify({"status":"error","message_id":"SC_API_002","message":f"Coureur introuvable: {e}"}), 404

    fields = rec.get("fields", {})

    email      = safe(fields, "Email", "")
    niveau     = safe(fields, "Niveau_normalisé", safe(fields, "Niveau", "Reprise"))
    objectif   = safe(fields, "Objectif_normalisé", safe(fields, "Objectif", "10K"))
    phase      = safe(fields, "Phase", "Base1")
    jours_disp = safe(fields, "📅 Jours_disponibles", safe(fields, "Jours_disponibles", []))
    date_start = parse_date_iso_or_ddmmyyyy(safe(fields, "Date début plan"))
    version    = int(safe(fields, "Version plan", 0) or 0)

    # -- Nb semaines (si Date_objectif dispo)
    nb_semaines = 8
    date_obj = safe(fields, "Date_objectif")
    if date_obj:
        try:
            d_obj = dtparse(str(date_obj).replace("Z","").replace("z","")).date()
            nb_semaines = weeks_between(datetime.today().date(), d_obj)
        except Exception:
            pass

    # -- RG nb jours hebdo
    jours_final = verifier_jours(fields)
    frequence = max(1, min(jours_final, len(jours_disp) if isinstance(jours_disp, list) else jours_final))

    # -- Structure par semaine issue de la table pivot
    structure = get_structure(phase, niveau, objectif, frequence)
    if not structure:
        return jsonify({
            "status":"error",
            "message_id":"SC_COACH_031",
            "message":"Aucune structure trouvée dans 📐 Structure Séances pour ces critères.",
        }), 200

    # -- Mapping clés -> (semaine, jour_nom, ordre)
    plan = assign_days(structure, jours_disp)

    # -- Index Séances types (métadonnées)
    types_dict = {}
    for r in TABLE_SEANCES_TYPES.all():
        f = r.get("fields", {})
        key = safe(f, "Clé séance")
        if not key:
            continue
        type_long = safe(f, "Type séance", f.get("Type"))
        # normalise éventuel multi-select
        if isinstance(type_long, list) and type_long:
            type_long = type_long[0]
        types_dict[key] = {
            "Nom": safe(f, "Nom séance", key),
            "Type_long": type_long,
            "Type_court": type_court_from_key_or_long(key, type_long),
            "Duree": safe(f, "Durée (min)", 0),
            "Coach": safe(f, "🧠 Message_coach (modèle)", f.get("🧠 Message coach") or ""),
            "Phase": safe(f, "Phase"),
        }

    # -- Récup des séances existantes du coureur (Link field → utilisez FIND + ARRAYJOIN)
    existing = TABLE_SEANCES.all(
        formula=f"FIND('{record_id}', ARRAYJOIN({{Coureur}}))"
    )
    archived = archive_records(existing, version) if existing else 0

    # -- Incrément de version
    new_version = version + 1
    TABLE_COUR.update(record_id, {"Version plan": new_version})

    # -- Création des séances + enregistrement mails (si tu veux piloter Make)
    created = 0
    mails = []

    for (semaine, jour_nom, ordre, cle) in plan:
        meta = types_dict.get(cle)
        if not meta:
            # clé non trouvée → séance placeholder EF
            meta = {
                "Nom": cle,
                "Type_long": "Endurance fondamentale",
                "Type_court": "EF",
                "Duree": 40,
                "Coach": "",
                "Phase": phase,
            }

        d = date_for_week_and_weekday(date_start, semaine, jour_nom)
        date_str = to_ddmmyyyy(d)

        # sécurité Type séance texte simple
        type_seance_text = meta["Type_court"]
        if isinstance(type_seance_text, list):
            type_seance_text = type_seance_text[0] if type_seance_text else ""

        TABLE_SEANCES.create({
            "Coureur": [record_id],
            "Clé séance": cle,
            "Nom séance": meta["Nom"],
            "Type séance": type_seance_text,        # texte simple
            "Phase": meta.get("Phase"),
            "Durée (min)": meta["Duree"],
            "Charge": None,                         # laisse Airtable/Make calculer si besoin
            "🧠 Message_coach": meta["Coach"],
            "Semaine": int(semaine),
            "Jour planifié": int(ordre),            # NUMÉRIQUE
            "Jour (nom)": jour_nom,
            "Date planifiée": date_str,             # dd/mm/yyyy (ICS/feedback)
            "Version plan": new_version
        })
        created += 1

        ics = build_ics(date_str, meta["Nom"], meta["Coach"])
        mails.append({
            "To": safe(fields, "Email", ""),
            "Subject": f"[SmartCoach] {meta['Nom']} – S{semaine} ({jour_nom})",
            "Body": f"S{semaine} – {jour_nom} ({date_str})\n\n{meta['Nom']}\n{meta['Coach']}",
            "ICS_Content": ics,
            "Status": "pending"
        })

    # Enregistre les mails en table si besoin de pipeline Make derrière
    for m in mails:
        try:
            TABLE_MAILS.create(m)
        except Exception:
            pass

    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_024",
        "message": f"✅ Nouveau plan généré — **Version {new_version}**\n{created} séances créées.",
        "nb_semaines": len(structure),
        "jours_par_semaine": frequence,
        "total": created,
        "archives": archived,
        "version_plan": new_version
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)