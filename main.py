import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from dateutil.parser import parse
from pyairtable import Table

# -------------------------
#   CONFIGURATION AIRTABLE
# -------------------------
API_KEY = os.environ.get("AIRTABLE_API_KEY")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

TABLE_COUR           = Table(API_KEY, BASE_ID, "👤 Coureurs")
TABLE_SEANCES        = Table(API_KEY, BASE_ID, "🏋️ Séances")
TABLE_ARCHIVES       = Table(API_KEY, BASE_ID, "🗄️ Archives")
TABLE_SEANCES_TYPES  = Table(API_KEY, BASE_ID, "📘 Séances types")
TABLE_STRUCTURE      = Table(API_KEY, BASE_ID, "📐 Structure Séances")
TABLE_MAILS          = Table(API_KEY, BASE_ID, "📬 Mails")

app = Flask(__name__)

# -------------------------
#   HELPERS
# -------------------------
JOUR_IDX = {"Lundi":0,"Mardi":1,"Mercredi":2,"Jeudi":3,"Vendredi":4,"Samedi":5,"Dimanche":6}

def safe(f, k, default=None):
    v = f.get(k)
    return default if v in (None, "", []) else v

def archive_records(records, version):
    """
    Archivage physique :
    - copie chaque séance dans 🗄️ Archives
    - conserve le lien Coureur (✱ validé hier)
    - historise via Version plan
    - supprime la séance active de 🏋️ Séances
    """
    count = 0
    for r in records:
        fields = r["fields"].copy()
        fields["Version plan"] = version
        TABLE_ARCHIVES.create(fields)
        TABLE_SEANCES.delete(r["id"])
        count += 1
    return count

def get_structure(phase, niveau, objectif, frequence):
    formula = f"""
        AND(
            {{Phase}} = '{phase}',
            {{Niveau}} = '{niveau}',
            {{Objectif}} = '{objectif}',
            {{Fréquence}} = {frequence}
        )
    """
    rows = TABLE_STRUCTURE.all(formula=formula)
    out = {}
    for r in rows:
        f = r["fields"]
        sem = int(f.get("Semaine"))
        cle = f.get("Clé séance")
        if not cle:
            continue
        out.setdefault(sem, []).append(cle)

    # SL en dernier dans la semaine
    for k, v in out.items():
        out[k] = sorted(v, key=lambda c: "SL" in c)

    return dict(sorted(out.items(), key=lambda x: x[0]))

def assign_days(structure, jours):
    if not jours:
        return []
    first = jours[0]
    last  = jours[-1]
    res = []
    for semaine, cles in structure.items():
        for cle in cles:
            jour = last if "SL" in cle else first
            res.append((semaine, jour, cle))
    return res

def date_from_week(date_start, semaine, jour_label):
    base = parse(date_start).date()
    start_week = base + timedelta(weeks=semaine-1)
    delta = (JOUR_IDX[jour_label] - start_week.weekday()) % 7
    d = start_week + timedelta(days=delta)
    return d.strftime("%d/%m/%Y")

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
        f"DESCRIPTION:{desc}",
        "END:VEVENT",
        "END:VCALENDAR"
    ])

# -------------------------
#   ROUTE PRINCIPALE
# -------------------------
@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    data = request.json
    record_id = data.get("record_id")

    coureur = TABLE_COUR.get(record_id)["fields"]
    email            = safe(coueur, "Email", "")
    niveau           = safe(coueur, "Niveau", "Reprise")
    objectif         = safe(coueur, "Objectif", "10K")
    phase            = safe(coueur, "Phase", "Base1")
    jours_dispo      = safe(coueur, "Jours disponibles", [])
    date_start       = safe(coueur, "Date début plan")
    version          = safe(coueur, "Version plan", 0) or 0

    if not date_start:
        return jsonify({"error":"Date début plan manquante"}), 400

    frequence = max(1, len(jours_dispo))

    structure = get_structure(phase, niveau, objectif, frequence)
    plan = assign_days(structure, jours_dispo)

    types_dict = {}
    for r in TABLE_SEANCES_TYPES.all():
        f = r["fields"]
        key = safe(f, "Clé séance")
        if key:
            types_dict[key] = {
                "Nom": safe(f, "Nom séance", key),
                "Type": safe(f, "Type séance", ""),
                "Duree": safe(f, "Durée (min)", 0),
                "Coach": safe(f, "🧠 Message coach", "")
            }

    existing = TABLE_SEANCES.all(formula=f"{{Coureur}} = '{record_id}'")
    archived = archive_records(existing, version) if existing else 0

    new_version = version + 1
    TABLE_COUR.update(record_id, {"Version plan": new_version})

    mails = []
    created = 0

    for (semaine, jour, cle) in plan:
        meta = types_dict.get(cle, {"Nom":cle,"Type":"","Duree":0,"Coach":""})
        date_str = date_from_week(date_start, semaine, jour)

        TABLE_SEANCES.create({
            "Coureur":[record_id],
            "Clé séance": cle,
            "Nom séance": meta["Nom"],
            "Type séance": meta["Type"],
            "Durée (min)": meta["Duree"],
            "🧠 Message_coach": meta["Coach"],
            "Semaine": semaine,
            "Jour planifié": jour,
            "Date": date_str,
            "Version plan": new_version
        })
        created += 1

        ics = build_ics(date_str, meta["Nom"], meta["Coach"])
        mails.append({
            "To": email,
            "Subject": f"[SmartCoach] {meta['Nom']} – S{semaine} ({jour})",
            "Body": f"Ta séance du {jour} (S{semaine}) est prévue le {date_str}.\n\n{meta['Nom']}\n{meta['Coach']}",
            "ICS_Content": ics,
            "Status": "pending"
        })

    for m in mails:
        TABLE_MAILS.create(m)

    return jsonify({
        "status":"ok",
        "message":f"✅ Plan généré — version {new_version}",
        "séances créées": created,
        "séances archivées": archived,
        "nb_semaines": len(structure),
        "jours/sem": frequence,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)