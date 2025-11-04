from flask import Flask, request, jsonify
from pyairtable import Api
import os
from datetime import datetime

app = Flask(__name__)

# ========= ENV VARS =========
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")                      # 🏃 Coureurs
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")                # 🏋️ Séances générées
TABLE_SEANCES_TYPES_NAME = os.environ.get("TABLE_SEANCES_TYPES")    # 📘 Séances types
TABLE_MODEL_NAME = "📐 Modèles"                                     # Table pilotage du plan

# Vérification des variables d’environnement
missing_env = [k for k, v in {
    "AIRTABLE_KEY": AIRTABLE_KEY,
    "BASE_ID": BASE_ID,
    "TABLE_COUR": TABLE_COUR_NAME,
    "TABLE_SEANCES": TABLE_SEANCES_NAME,
    "TABLE_SEANCES_TYPES": TABLE_SEANCES_TYPES_NAME
}.items() if not v]

if missing_env:
    raise RuntimeError(f"[CONFIG] Variables d’environnement manquantes: {', '.join(missing_env)}")

# ========= AIRTABLE INIT =========
api = Api(AIRTABLE_KEY)

TABLE_COUR = api.table(BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = api.table(BASE_ID, TABLE_SEANCES_NAME)
TABLE_SEANCES_TYPES = api.table(BASE_ID, TABLE_SEANCES_TYPES_NAME)
TABLE_MODEL = api.table(BASE_ID, TABLE_MODEL_NAME)

# ========= UTILS =========
def weeks_between(d1, d2):
    try:
        return max(1, round((d2 - d1).days / 7))
    except:
        return 8

def get_modele_seance(objectif, niveau, semaine, jour):
    """
    Récupère la Clé Séance définie dans la table de pilotage 📐 Modèles
    """
    formula = (
        f"AND("
        f"{{Objectif}} = '{objectif}',"
        f"{{Niveau}} = '{niveau}',"
        f"{{Semaine}} = {semaine},"
        f"{{Jour planifié}} = {jour}"
        f")"
    )

    rows = TABLE_MODEL.all(formula=formula)
    if not rows:
        raise ValueError(f"Aucune séance définie pour : Objectif={objectif}, Niveau={niveau}, S={semaine}, J={jour}")

    # Clé séance est un lien → liste → on prend le premier ID
    clé = rows[0]["fields"]["Clé séance"][0]
    return clé

# ========= API ENDPOINT =========
@app.post("/generate_by_id")
def generate_by_id():
    data = request.json
    record_id = data.get("id")

    coureur = TABLE_COUR.get(record_id)
    fields = coureur["fields"]

    nb_semaines = fields.get("Nb_semaines") or 8
    jours_final = fields.get("📅Nb_jours_dispo") or 2

    try:
        nb_semaines = int(nb_semaines)
        jours_final = int(jours_final)
    except:
        return jsonify({"status": "error", "message": "Champs invalides"}), 400

    total_crees = 0
    sorties = []

    for semaine in range(1, nb_semaines + 1):
        for j in range(1, jours_final + 1):

            clé = get_modele_seance("10K", "Reprise", semaine, j)
            st = TABLE_SEANCES_TYPES.get(clé)["fields"]

            payload = {
                "Coureur": [record_id],
                "NomSéance": st.get("Nom séance"),
                "Clé séance": st.get("Clé séance"),
                "Phase": st.get("Phase"),
                "type": seance_type.get("Type séance")[0] if seance_type.get("Type séance") else None,
                "Durée (min)": st.get("Durée (min)"),
                "Charge": st.get("Charge", 2),
                "🧠 Message_coach": st.get("🧠 Message_coach (modèle)"),
                "Semaine": semaine,
                "Jour planifié": j
            }

            TABLE_SEANCES.create(payload)
            sorties.append(payload)
            total_crees += 1

    return jsonify({
        "status": "ok",
        "message": f"✅ {total_crees} séances générées ({nb_semaines} sem × {jours_final}/sem).",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_final,
        "total": total_crees,
        "message_id": "SC_COACH_021"
    })

# ========= RENDER ENTRYPOINT =========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))