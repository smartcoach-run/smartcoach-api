from flask import Flask, request, jsonify
from pyairtable import Table
from datetime import datetime
import os

app = Flask(__name__)

# ========= ENV =========
API_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")
TABLE_ARCHIVES_NAME = os.environ.get("TABLE_ARCHIVES")
TABLE_MODELES_NAME = os.environ.get("TABLE_SEANCES_TYPES") or os.environ.get("TABLE_MODELES")
TABLE_VDOT_NAME = "VDOT_reference"

if not all([API_KEY, BASE_ID, TABLE_COUR_NAME, TABLE_SEANCES_NAME, TABLE_ARCHIVES_NAME, TABLE_MODELES_NAME]):
    raise RuntimeError("🚨 Variables d’environnement manquantes. Vérifie AIRTABLE_KEY, BASE_ID et les TABLE_*.")

# ========= TABLES =========
TABLE_COUR = Table(API_KEY, BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = Table(API_KEY, BASE_ID, TABLE_SEANCES_NAME)
TABLE_ARCHIVES = Table(API_KEY, BASE_ID, TABLE_ARCHIVES_NAME)
TABLE_MODELES = Table(API_KEY, BASE_ID, TABLE_MODELES_NAME)
TABLE_VDOT = Table(API_KEY, BASE_ID, TABLE_VDOT_NAME)

# ========= HELPERS =========
ZONE_MAP = {
    # Endurance
    "footing": "E",
    "endurance": "E",
    "endurance fondamentale": "E",
    "récup": "E",
    "recup": "E",
    "souplesse": "E",
    # Marathon / modéré
    "sortie longue": "M",
    "endurance + rythme": "M",
    "marathon": "M",
    # Seuil / Tempo
    "seuil": "T",
    "tempo": "T",
    # Intervalles / VMA
    "intervalles": "I",
    "vma": "I",
    # Technique (par défaut -> Récup)
    "technique": "R",
}

def pick_zone_from_type(type_value):
    """
    Convertit 'Type séance' (multi-select ou texte) en zone VDOT (E/M/T/I/R).
    On prend la première valeur mappable rencontrée.
    """
    if not type_value:
        return None
    values = type_value if isinstance(type_value, list) else [type_value]
    for val in values:
        slug = str(val).strip().lower()
        # exemple: "Endurance + rythme" -> match "endurance + rythme"
        for key, zone in ZONE_MAP.items():
            if key in slug:
                return zone
    return None

def get_allure_from_vdot(vdot_value, zone):
    """
    Renvoie (allure, vitesse) depuis VDOT_reference pour la zone demandée (E/M/T/I/R).
    """
    if not vdot_value or not zone:
        return None, None

    # Récup la ligne VDOT exacte (VDOT est numérique en table)
    try:
        vdot_float = float(vdot_value)
        # VDOT est souvent entier; on le round au plus proche pour match
        vdot_int = int(round(vdot_float))
    except Exception:
        return None, None

    rec = TABLE_VDOT.first(formula=f"{{VDOT}} = {vdot_int}")
    if not rec:
        return None, None

    fields = rec.get("fields", {})
    allure_field = f"Allure_{zone}"
    vitesse_field = f"Vitesse_{zone}"
    return fields.get(allure_field), fields.get(vitesse_field)

def list_len(value):
    if isinstance(value, list):
        return len(value)
    return 0

def weeks_between_today_and(date_iso):
    try:
        target = datetime.fromisoformat(str(date_iso).replace("Z","").replace("z",""))
        days = (target - datetime.today()).days
        return max(1, round(days/7))
    except Exception:
        return 8

def find_existing_seances(record_id):
    # filtre robuste sur champ link (Coureur) via ARRAYJOIN
    formula = f"FIND('{record_id}', ARRAYJOIN({{Coureur}}))"
    return TABLE_SEANCES.all(formula=formula)

def archive_records(existing, version):
    archived = 0
    for rec in existing:
        f = rec.get("fields", {})
        TABLE_ARCHIVES.create({
            "ID séance originale": rec.get("id"),
            "Coureur": f.get("Coureur"),
            "Nom séance": f.get("Nom séance"),
            "Type séance": f.get("Type séance"),
            "Durée (min)": f.get("Durée (min)"),
            "Charge": f.get("Charge"),
            "Allure / zone": f.get("Allure / zone"),
            "Phase": f.get("Phase"),
            "Clé séance": f.get("Clé séance"),
            "🧠 Message coach": f.get("🧠 Message coach"),
            "Semaine": f.get("Semaine"),
            "Jour planifié": f.get("Jour planifié"),
            "Version plan": version,
            "Date archivage": datetime.utcnow().isoformat(),
            "Source": "auto-archive"
        })
        archived += 1

    # suppression une par une (pyairtable batch delete optionnelle)
    for rec in existing:
        TABLE_SEANCES.delete(rec["id"])
    return archived


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
            "message": "⚠️ record_id manquant dans le payload"
        }), 400

    # ===== Coureur =====
    try:
        coureur = TABLE_COUR.get(record_id).get("fields", {})
    except Exception as e:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_002",
            "message": f"❌ Coureur introuvable: {e}"
        }), 404

    # Champs coureur (tolérants)
    jours_dispo = coureur.get("📅 Jours disponibles") or coureur.get("📅 Jours_disponibles") or []
    nb_semaines = int(coureur.get("⏱️ Nb semaines", 8)) if str(coureur.get("⏱️ Nb semaines", "")).strip() != "" else 8
    vdot = coureur.get("VDOT") or coureur.get("VDOT_utilisé")

    # ===== Version plan =====
    version_actuelle = int(coureur.get("Version plan") or 0)
    nouvelle_version = version_actuelle + 1

    # Archiver si des séances existent déjà
    existing = find_existing_seances(record_id)
    nb_archives = 0
    if existing:
        nb_archives = archive_records(existing, version_actuelle)

    # Appliquer la version au coureur AVANT création
    TABLE_COUR.update(record_id, {"Version plan": nouvelle_version})

    # ===== Récup modèles =====
    model_records = TABLE_MODELES.all()
    modeles = [m.get("fields", {}) for m in model_records]

    # ===== Construction & création =====
    jours_par_semaine = list_len(jours_dispo)
    total_crees = 0

    if jours_par_semaine > 0:
        # tri simple par Charge puis Durée
        modeles_sorted = sorted(modeles, key=lambda x: (x.get("Charge", 2), x.get("Durée (min)", 30)))

        for semaine in range(1, nb_semaines + 1):
            bloc = modeles_sorted[:jours_par_semaine]
            for j, f in enumerate(bloc, start=1):
                nom = f.get("Nom séance")
                type_seance_raw = f.get("Type séance")
                phase = f.get("Phase")
                duree = f.get("Durée (min)")
                charge = f.get("Charge", 2)
                message = f.get("🧠 Message_coach (modèle)")
                cle = f.get("Clé séance")

                # zone VDOT depuis Type séance
                zone = pick_zone_from_type(type_seance_raw)
                allure, _ = get_allure_from_vdot(vdot, zone)  # vitesse non stockée pour l’instant

                # si multi-select → on garde la 1ère valeur pour la lisibilité
                if isinstance(type_seance_raw, list) and type_seance_raw:
                    type_seance_final = type_seance_raw[0]
                else:
                    type_seance_final = type_seance_raw

                TABLE_SEANCES.create({
                    "Coureur": [record_id],
                    "Nom séance": nom,
                    "Type séance": type_seance_final,
                    "Durée (min)": duree,
                    "Charge": charge,
                    "Phase": phase,
                    "Clé séance": cle,
                    "🧠 Message coach": message,
                    "Semaine": semaine,
                    "Jour planifié": j,
                    "Version plan": nouvelle_version
                })
                total_crees += 1

    # ===== Réponse =====
    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_024",
        "message": f"✅ Nouveau plan généré — **Version {nouvelle_version}**\n{total_crees} séances créées ({nb_semaines} sem × {jours_par_semaine}/sem).",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_par_semaine,
        "total": total_crees,
        "version_plan": nouvelle_version,
        "archives": nb_archives
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)