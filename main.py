import os
from flask import Flask, request, jsonify
from pyairtable import Table, Api
from datetime import datetime, timedelta

app = Flask(__name__)

# ========= ENV VARS =========
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")                     # 👤 Coureurs
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")               # 🏋️ Séances (générées)
TABLE_ARCHIVES_NAME = os.environ.get("TABLE_ARCHIVES")             # 🗄️ Archives Séances
TABLE_MODELES_NAME = os.environ.get("TABLE_MODELES")               # (optionnel)
TABLE_SEANCES_TYPES_NAME = os.environ.get("TABLE_SEANCES_TYPES")   # 📘 Séances types (référentiel)
RENDER_DOMAIN = os.environ.get("RENDER_DOMAIN", "smartcoach-api.onrender.com")

missing_env = [k for k, v in {
    "AIRTABLE_KEY": AIRTABLE_KEY,
    "BASE_ID": BASE_ID,
    "TABLE_COUR": TABLE_COUR_NAME,
    "TABLE_SEANCES": TABLE_SEANCES_NAME,
    "TABLE_ARCHIVES": TABLE_ARCHIVES_NAME,
    "TABLE_SEANCES_TYPES": TABLE_SEANCES_TYPES_NAME
}.items() if not v]
if missing_env:
    raise RuntimeError(f"[CONFIG] Variables d’environnement manquantes: {', '.join(missing_env)}")

# ========= AIRTABLE CLIENTS =========
# (on garde Table(...) même si déprécié : simple et déjà en place chez toi)
TABLE_COUR = Table(AIRTABLE_KEY, BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = Table(AIRTABLE_KEY, BASE_ID, TABLE_SEANCES_NAME)
TABLE_ARCHIVES = Table(AIRTABLE_KEY, BASE_ID, TABLE_ARCHIVES_NAME)
TABLE_MODELES = Table(AIRTABLE_KEY, BASE_ID, TABLE_MODELES_NAME) if TABLE_MODELES_NAME else None
TABLE_SEANCES_TYPES = Table(AIRTABLE_KEY, BASE_ID, TABLE_SEANCES_TYPES_NAME)


# ========= HELPERS =========
def weeks_between(d1: datetime, d2: datetime) -> int:
    """Nombre de semaines arrondi, min=1."""
    try:
        return max(1, round((d2 - d1).days / 7))
    except Exception:
        return 8  # fallback


def parse_days_string(raw: str):
    """Convertit 'vendredi, dimanche' -> [4,6]."""
    mapping = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
        "vendredi": 4, "samedi": 5, "dimanche": 6
    }
    if not raw:
        return [2, 6]  # fallback mercredi/dimanche
    days = []
    for part in str(raw).split(","):
        k = part.strip().lower()
        if k in mapping:
            days.append(mapping[k])
    return sorted(days) or [2, 6]


def assign_session_dates(sessions, start_date_iso: str, days_index):
    """
    sessions: liste de payloads dans l'ordre de génération
    start_date_iso: 'YYYY-MM-DD'
    days_index: liste d'index (0=lundi..6=dimanche), ex [4,6]
    Retourne sessions enrichies avec "Date séance" (dd/mm/yyyy)
    """
    # Base de départ : aligne la première semaine sur start_date
    start = datetime.fromisoformat(start_date_iso).date()

    out = []
    week = 0
    i = 0
    total = len(sessions)

    while i < total:
        # date base de la semaine
        base_week_date = start + timedelta(weeks=week)
        for d in days_index:
            # calcule date du "d" dans la semaine de base_week_date
            delta = (d - base_week_date.weekday()) % 7
            date_seance = base_week_date + timedelta(days=delta)

            if i < total:
                s = sessions[i].copy()
                # format dd/mm/yyyy pour Airtable (champ texte conseillé)
                s["Date séance"] = date_seance.strftime("%d/%m/%Y")
                out.append(s)
                i += 1
        week += 1
    return out


def archive_records(records_to_archive: list, record_id: str, version_actuelle: int) -> int:
    """
    Copie chaque séance existante vers 🗄️ Archives Séances.
    Retourne le nombre d'archives créées.
    """
    nb = 0
    for rec in records_to_archive:
        f = rec.get("fields", {})
        payload = {
            # Liens et traces
            "Coureur": [record_id],
            "ID séance originale": rec.get("id"),
            "Version plan": f.get("Version plan"),
            "Source": "auto-archive",

            # Champs métiers (on copie large, si le champ existe il se remplira)
            "Nom séance": f.get("Nom séance"),
            "Type séance": f.get("Type séance"),
            "Phase": f.get("Phase"),
            "Clé séance": f.get("Clé séance"),
            "Allure / zone": f.get("Allure / zone"),
            "Durée (min)": f.get("Durée (min)"),
            "Charge": f.get("Charge"),
            "Semaine": f.get("Semaine"),
            "Jour planifié": f.get("Jour planifié"),
            "Date séance": f.get("Date séance"),
            "🧠 Message coach": f.get("🧠 Message coach"),
            # Date d'archivage en ISO simple (texte)
            "Date archivage": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        TABLE_ARCHIVES.create(payload)
        nb += 1
    return nb


def iso_today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def build_ics_content(dated_sessions: list, plan_version: int) -> str:
    """
    Construit un ICS simple (VCALENDAR) sans dépendance externe.
    Chaque séance = VEVENT avec date début à 07:00 locale et durée par défaut 60min si non renseignée.
    """
    def dtstamp():
        return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    def dt_local(date_str_ddmmyyyy: str, hour: int = 7, minute: int = 0):
        # Convertit "dd/mm/yyyy" -> "YYYYMMDDTHHMMSS"
        d = datetime.strptime(date_str_ddmmyyyy, "%d/%m/%Y")
        return d.strftime(f"%Y%m%dT{hour:02d}{minute:02d}00")

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//SmartCoach//Plan Auto//FR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]
    for s in dated_sessions:
        name = s.get("Nom séance") or "Séance"
        desc = s.get("🧠 Message coach") or ""
        date_txt = s.get("Date séance")  # dd/mm/yyyy
        start = dt_local(date_txt, 7, 0)
        # Durée en minutes si dispo
        duree = s.get("Durée (min)") or 60
        # Fin = début + durée
        dstart = datetime.strptime(date_txt, "%d/%m/%Y").replace(hour=7, minute=0, second=0)
        dend = dstart + timedelta(minutes=int(duree))
        end = dend.strftime("%Y%m%dT%H%M%S")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{s.get('Clé séance','')}-{start}-v{plan_version}@smartcoach",
            f"DTSTAMP:{dtstamp()}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{name} — SmartCoach v{plan_version}",
            f"DESCRIPTION:{desc.replace('\\n', ' ')}",
            "END:VEVENT"
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def save_ics(dated_sessions: list, record_id: str, plan_version: int) -> str:
    """
    Sauvegarde le contenu ICS dans /static/calendars/<recordId>_v<version>.ics
    Retourne le chemin relatif pour construire l'URL publique.
    """
    folder = os.path.join("static", "calendars")
    os.makedirs(folder, exist_ok=True)
    filename = f"{record_id}_v{plan_version}.ics"
    path = os.path.join(folder, filename)
    content = build_ics_content(dated_sessions, plan_version)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"static/calendars/{filename}"


def verifier_jours(fields: dict) -> int:
    """
    Calcule le nb de jours hebdo final.
    - Si '📅Nb_jours_dispo' existe => int
    - Sinon, déduit depuis 'Jours_cible' (ou '📅 Jours_disponibles') en comptant le nb de jours listés
    """
    jours_dispo = fields.get("📅Nb_jours_dispo")
    if jours_dispo is not None:
        try:
            return max(1, int(jours_dispo))
        except Exception:
            pass

    # fallback : compter le nombre de jours dans la chaîne
    raw = fields.get("Jours_cible") or fields.get("📅 Jours_disponibles") or ""
    days = [x.strip() for x in str(raw).split(",") if x.strip()]
    return max(1, len(days)) or 1


@app.get("/")
def health():
    return "SmartCoach API active ✅"


@app.post("/generate_by_id")
def generate_by_id():
    """
    Scénario 1 : Génère un plan depuis un coureur
    - vérifie/augmente Version plan
    - archive l'ancien plan
    - lit 📘 Séances types selon critères
    - écrit 🏋️ Séances avec dates
    - génère un ICS
    """
    data = request.json or {}
    record_id = data.get("id")
    if not record_id:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_001",
            "message": "⚠️ Aucun ID de coureur reçu.",
            "expected_format": {"id": "recXXXXXXXXXXXXXX"}
        }), 400

    # ---- Récup coureur
    try:
        rec = TABLE_COUR.get(record_id)
    except Exception as e:
        return jsonify({"status": "error", "message_id": "SC_API_002", "message": f"❌ Coureur introuvable: {e}"}), 404

    fields = rec.get("fields", {})
    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = fields.get("VDOT_utilisé")
    date_debut_plan = fields.get("Date début plan")  # ISO YYYY-MM-DD (confirmé présent)
    if not date_debut_plan:
        return jsonify({"status": "error", "message_id": "SC_API_010", "message": "❌ Date début plan manquante"}), 400

    # nb semaines (si Date_objectif dispo)
    nb_semaines = 8
    date_obj = fields.get("Date_objectif")
    if date_obj:
        try:
            d_obj = datetime.fromisoformat(str(date_obj).replace("Z", "").replace("z", ""))
            nb_semaines = weeks_between(datetime.today(), d_obj)
        except Exception:
            pass

    # nb jours / semaine
    jours_final = verifier_jours(fields)

    # jours disponibles en indices
    jours_raw = fields.get("Jours_cible") or fields.get("📅 Jours_disponibles") or ""
    jours_index = parse_days_string(jours_raw)

    # ---- Version plan (coureurs)
    version_actuelle = int(fields.get("Version plan") or 0)
    nouvelle_version = version_actuelle + 1
    TABLE_COUR.update(record_id, {"Version plan": nouvelle_version})

    # ---- Archive ancien plan (toutes séances du coureur avec Version plan == version_actuelle)
    archives_count = 0
    if version_actuelle > 0:
        # Trouver les séances existantes du coureur
        formula_existing = f"AND({{Version plan}} = {version_actuelle}, FIND('{record_id}', ARRAYJOIN({{Coureur}})))"
        existing = TABLE_SEANCES.all(formula=formula_existing) or []
        if existing:
            archives_count = archive_records(existing, record_id, version_actuelle)
            # supprimer les anciennes séances pour repartir propre
            for r in existing:
                try:
                    TABLE_SEANCES.delete(r.get("id"))
                except Exception:
                    pass

    # ---- Lire référentiel 📘 Séances types
    try:
        all_types = TABLE_SEANCES_TYPES.all()
    except Exception as e:
        return jsonify({"status": "error", "message_id": "SC_API_003", "message": f"❌ Lecture Séances types: {e}"}), 500

    # Filtrage
    PHASES_AUTORISEES = ["Prépa générale", "Progression", "Spécifique", "Affûtage", "Base1", "Base2"]
    pool = []
    for s in all_types:
        f = s.get("fields", {})
        if f.get("Mode") != "Running":
            continue
        if f.get("Phase") not in PHASES_AUTORISEES:
            continue

        niveaux = f.get("Niveau") or []
        if isinstance(niveaux, str):
            niveaux = [niveaux]
        if niveau and niveaux and (niveau not in niveaux):
            continue

        objectifs = f.get("Objectif") or []
        if isinstance(objectifs, str):
            objectifs = [objectifs]
        if objectif and objectifs and (objectif not in objectifs):
            continue

        # Fenêtre VDOT si présente
        try:
            vmin = f.get("VDOT_min")
            vmax = f.get("VDOT_max")
            if vmin is not None and vmax is not None and vdot is not None:
                dv = float(vdot)
                if not (float(vmin) <= dv <= float(vmax)):
                    continue
        except Exception:
            pass

        pool.append(f)

    if not pool:
        return jsonify({
            "status": "error",
            "message_id": "SC_COACH_012",
            "message": "Aucune séance adaptée trouvée. Référentiel à compléter.",
            "seances": []
        }), 200

    # tri simple (Charge puis Durée)
    pool = sorted(pool, key=lambda x: (x.get("Charge", 2), x.get("Durée (min)", 30)))

    # ---- Génération brute (sans modèles fixes) : on prend les 'jours_final' premières de pool pour chaque semaine
    # (Tu peux substituer ici par la logique de catégories & alternance quand tu veux)
    plan_payloads = []
    for semaine in range(1, nb_semaines + 1):
        bloc = pool[:max(1, jours_final)]
        for j, f in enumerate(bloc, start=1):
            # source du message : "Message (template)" côté Séances types
            message_src = f.get("Message (template)") or ""
            payload = {
                "Coureur": [record_id],
                "Nom séance": f.get("Nom séance"),
                "Type séance": f.get("Type séance") or f.get("Type"),
                "Phase": f.get("Phase"),
                "Clé séance": f.get("Clé séance"),
                "Allure / zone": f.get("Allure / zone"),
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge", 2),
                "Semaine": semaine,
                "Jour planifié": j,
                "🧠 Message coach": message_src,
                "Version plan": nouvelle_version
            }
            plan_payloads.append(payload)

    # ---- Datation des séances
    plan_dated = assign_session_dates(plan_payloads, date_debut_plan, jours_index)

    # ---- Écriture Airtable
    total_crees = 0
    for p in plan_dated:
        TABLE_SEANCES.create(p)
        total_crees += 1

    # ---- ICS
    ics_relpath = save_ics(plan_dated, record_id, nouvelle_version)
    ics_url = f"https://{RENDER_DOMAIN}/{ics_relpath}"

    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_024",
        "message": f"✅ Nouveau plan généré — **Version {nouvelle_version}**\n{total_crees} séances créées ({nb_semaines} sem × {jours_final}/sem).",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_final,
        "total": total_crees,
        "version_plan": nouvelle_version,
        "archives": archives_count,
        "ics_url": ics_url
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)