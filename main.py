# -*- coding: utf-8 -*-
"""
SmartCoach API – Génération de séances (Scénario 1)
---------------------------------------------------
- Lit le profil du coureur (👤 Coureurs)
- Détermine la structure (📐 Structure Séances) en fonction Phase/Niveau/Objectif/Fréquence
- Choisit les séances concrètes (📘 Séances types)
- Archive l'existant (📦 Archives Séances), incrémente la Version, crée les nouvelles (🏋️ Séances)
- Champs compatibles avec Type séance (texte) et Type séance (court)

Env vars utiles (avec fallbacks lisibles) :
- AIRTABLE_KEY, BASE_ID
- TABLE_COUR, TABLE_SEANCES, TABLE_ARCHIVES, TABLE_SEANCES_TYPES, TABLE_STRUCTURE, TABLE_MAILS
- PORT (optionnel)
"""

from datetime import datetime, timedelta, timezone
import os
import re
from typing import List, Dict, Any, Optional, Tuple

from flask import Flask, request, jsonify
from pyairtable import Table
from pyairtable.formulas import AND, match

# -----------------------------------------------------------------------------
# Utils ENV + Tables
# -----------------------------------------------------------------------------

def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v and v.strip() else default

AIRTABLE_KEY = _env("AIRTABLE_KEY", _env("AIRTABLE_KEY", ""))
BASE_ID      = _env("BASE_ID", "")

if not AIRTABLE_KEY or not BASE_ID:
    raise RuntimeError("AIRTABLE_KEY / BASE_ID manquants en variables d'environnement.")

def get_table(env_name: str, *fallback_names: str) -> Table:
    """
    Récupère une Table Airtable en priorité via le nom stocké en ENV.
    Sinon essaie chaque fallback dans l'ordre.
    """
    table_name = os.environ.get(env_name)
    if table_name and table_name.strip():
        try:
            return Table(AIRTABLE_KEY, BASE_ID, table_name.strip())
        except Exception:
            pass

    # essais en cascade
    last_err = None
    for fb in fallback_names:
        try:
            return Table(AIRTABLE_KEY, BASE_ID, fb)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError(f"Impossible d'ouvrir la table {env_name}")

# Tables (avec libellés FR compatibles avec tes captures)
TABLE_COUR                  = get_table("TABLE_COUR"                    , "👤 Coureurs", "Coureurs")
TABLE_SEANCES               = get_table("TABLE_SEANCES"                 , "🏋️ Séances", "Séances")
TABLE_ARCHIVES              = get_table("TABLE_ARCHIVES"                , "📦 Archives Séances", "Archives Séances", "Archives")
TABLE_SEANCES_TYPES         = get_table("TABLE_SEANCES_TYPES"           , "📘 Séances types", "Séances types")
TABLE_STRUCTURE             = get_table("TABLE_STRUCTURE"               , "📐 Structure Séances", "Structure Séances")
TABLE_MAILS                 = get_table("TABLE_MAILS"                   , "✉️ Mails", "Mails")  # Optionnel, pas utilisé ici
TABLE_MESSAGES_SMARTCOACH   = get_table("TABLE_MESSAGES_SMARTCOACH"     , "🗂️ Messages SmartCoach", "Messages SmartCoach")
TABLE_GROUPES               = get_table("TABLE_GROUPES"                 , "👥 Groupes", "Groupes")

# -----------------------------------------------------------------------------
# Petits helpers
# -----------------------------------------------------------------------------

WEEKDAYS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

PHASE_KEY = {
    "Prépa générale": "PG",
    "Prépa spécifique": "PS",
    "Affûtage": "AF"
}

def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def parse_date_ddmmyyyy(value: str) -> datetime:
    """
    Gère automatiquement :
    - dd/mm/yyyy (format formulaire)
    - yyyy-mm-dd (format Airtable natif)
    - datetime déjà parsée
    - fallback = aujourd’hui UTC
    """
    if not value:
        return datetime.now(timezone.utc)

    # Si déjà datetime → on renvoie tel quel
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    value = str(value).strip()

    # Format Airtable → yyyy-mm-dd
    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        try:
            y, m, d = value.split("-")
            return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
        except Exception:
            pass

    # Format dd/mm/yyyy
    if "/" in value:
        try:
            d, m, y = value.split("/")
            return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
        except Exception:
            pass

    # Fallback robuste
    return datetime.now(timezone.utc)

def jours_dispo(fields: Dict[str, Any]) -> List[str]:
    # Jours_disponibles (ex : ["Vendredi","Dimanche"])
    j = fields.get("📅 Jours_disponibles") or fields.get("Jours_disponibles") or fields.get("Jours disponibles") or []
    if not isinstance(j, list):  # si Multi-select renvoie str → le convertir
        return []
    # Conserver l'ordre tel que fourni
    return [x for x in j if x in WEEKDAYS_FR]

def int_field(fields: Dict[str, Any], *names: str, default: int = 0) -> int:
    for n in names:
        v = fields.get(n)
        if v is None or v == "":
            continue
        try:
            return int(v)
        except Exception:
            pass
    return default

def first_nonempty(fields: Dict[str, Any], *names: str, default=None):
    for n in names:
        if n in fields and fields[n] not in (None, ""):
            return fields[n]
    return default

def pick_session_from_type(short_type: str):
    """
    Fallback : récupère une séance type via le champ 'Type séance (court)'
    dans 📘 Séances types.
    """
    if not short_type:
        return None
    formula = f"{{Type séance (court)}} = '{short_type}'"
    rows = TABLE_SEANCES_TYPES.all(formula=formula)
    return rows[0] if rows else None

# ---- Messages Coach helpers ----
def safe_field(d: dict, candidates):
    """Retourne le premier nom de champ existant parmi candidates dans un dict 'fields' Airtable."""
    for name in candidates:
        if name in d:
            return name
    return None


def get_message_coach_for(phase: str, semaine: int, niveau: str, objectif: str):
    """
    Sélectionne le message coach via la colonne ID_Message dans 🗂️ Messages SmartCoach.
    Format attendu : ID_Message = "<phase>|S<semaine>|<niveau>|<objectif>"
    Exemple : "Prépa générale|S2|Débutant|10K"
    """
    # Normalisation légère
    phase_key = phase.strip()
    niveau_key = niveau.strip()
    obj_key   = objectif.strip()
    week_key  = f"S{semaine}"

    # Construction exacte de l'ID_Message
    id_msg = f"{phase_key}|{week_key}|{niveau_key}|{obj_key}"

    row = TABLE_MESSAGES_SMARTCOACH.first(formula=f"{{ID_Message}} = '{id_msg}'")
    if not row:
        # fallback (sans objectif)
        id_msg2 = f"{phase_key}|{week_key}|{niveau_key}"
        row = TABLE_MESSAGES_SMARTCOACH.first(formula=f"{{ID_Message}} = '{id_msg2}'")
        if not row:
            return ""

    fields = row.get("fields", {})
    return (
        fields.get("Message (template)") or
        fields.get("Message coach") or
        fields.get("Message") or
        ""
    )

def get_weekly_message(semaine: int):
    # S1->M1, S2->M2, S3->M3, S4->M4, S5->M1, etc.
    code = f"M{((semaine - 1) % 4) + 1}"
    row = TABLE_MESSAGES_SMARTCOACH.first(formula=f"{{ID_Message}} = '{code}'")
    if not row:
        return ""
    fields = row.get("fields", {})
    return fields.get("Message (template)", "") or fields.get("Message", "") or ""

# -----------------------------------------------------------------------------
# Sélection de structure + pick séance type
# -----------------------------------------------------------------------------

def get_structure_rows(phase: str):
    """
    Récupère l'ordre des séances pour une phase donnée
    depuis 📐 Structure Séances.
    Base1 / Base2 → mappés sur 'Prépa générale'.
    """
    phase_lookup = "Prépa générale" if phase in ("Base1", "Base2") else phase
    formula = f"{{Phase}} = '{phase_lookup}'"
    rows = TABLE_STRUCTURE.all(formula=formula)
    if not rows:
        raise ValueError(f"Aucune structure trouvée pour Phase={phase} (lookup={phase_lookup})")
    return sorted(rows, key=lambda r: r.get("fields", {}).get("Ordre", 0))

def OR_compat(*args):
    # petit OR qui fonctionne comme pyairtable.formulas.OR (mais inline)
    # Note : on peut imbriquer les AND/OR via Airtable, ici simplif.
    from pyairtable.formulas import OR
    return OR(*args)

# Mapping Type séance (court) -> Type séance (Airtable multi-select)
TYPE_MAP = {
    "EF": "Footing",
    "TECH": "Technique",
    "SL": "Sortie longue",
    "SEU": "Seuil",
    "VMA": "VMA",
    "AS10": "AS10",
    "OFF": "Repos",
    "VEILLE": "Activation légère",
    "RACE": "Course",
    "ACT": "Activation",
}


# -----------------------------------------------------------------------------
# Archivage
# -----------------------------------------------------------------------------

def archive_existing_for_runner(record_id: str, version_actuelle: int) -> int:
    """
    Archive toutes les séances du coureur, puis supprime.
    Écrit "Version plan" en copie et la date d’archivage.
    """
    if not record_id:
        return 0

    existing = TABLE_SEANCES.all(formula=f"FIND('{record_id}', ARRAYJOIN({{Coureur}}, ','))")
    if not existing:
        return 0

    n = 0
    now_iso = to_utc_iso(datetime.now(timezone.utc))

    for rec in existing:
        f = rec.get("fields", {})
        try:
            TABLE_ARCHIVES.create({
                "ID séance originale": rec.get("id"),
                "Coureur": [record_id],
                "Nom séance": f.get("Nom séance"),
                "Type séance": f.get("Type séance"),
                "Type séance (court)": f.get("Type séance (court)"),
                "Phase": f.get("Phase"),
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge"),
                "Allure / zone": f.get("Allure / zone"),
                "Détails JSON": f,  # trace utile
                "Version plan": version_actuelle,
                "Date archivage": now_iso,
                "Source": "auto-archive"
            })
            TABLE_SEANCES.delete(rec["id"])
            n += 1
        except Exception:
            # on continue, on ne bloque pas toute l'opération
            pass
    return n

# -----------------------------------------------------------------------------
# Génération des dates (à partir de Date début plan + jours dispo)
# -----------------------------------------------------------------------------

def generate_dates(start_date: datetime, nb_semaines: int, jours: List[str]) -> List[Tuple[int, str, datetime]]:
    """
    Retourne une liste (semaine_idx, jour_label, date_obj) triée par date croissante.
    - start_date = lundi 1er essai ? Non → on garde la date et on place la 1ère occurrence
      du jour demandé ≥ start_date, puis semaine par semaine.
    """
    # Map jour->offset weekday (0=Monday..6=Sunday)
    idx_by_label = {lbl: i for i, lbl in enumerate(WEEKDAYS_FR)}

    out = []
    for w in range(nb_semaines):
        # base de la semaine w = start_date + 7*w
        base_w = start_date + timedelta(days=7*w)
        for jlabel in jours:
            target_dow = idx_by_label[jlabel]  # 0..6
            # trouver le prochain 'target_dow' >= base_w
            offset = (target_dow - base_w.weekday()) % 7
            d = base_w + timedelta(days=offset)
            out.append((w+1, jlabel, d))

    out.sort(key=lambda x: x[2])  # tri par date
    return out

# -----------------------------------------------------------------------------
# Flask
# -----------------------------------------------------------------------------

app = Flask(__name__)

@app.get("/")
def root():
    return "SmartCoach API – OK", 200

@app.get("/health")
def health():
    return jsonify(ok=True, t=to_utc_iso(datetime.now(timezone.utc)))

def get_message_coach(message_key):
    formula = f"{{Clé Message}} = '{message_key}'"
    records = TABLE_MESSAGES_COACH.all(formula=formula)
    if records:
        return records[0]["fields"].get("Message (template)", "")
    return ""

# -----------------------------------------------------------------------------
# Endpoint principal
# -----------------------------------------------------------------------------

@app.post("/generate_by_id")
def generate_by_id():
    """
    JSON attendu : { "record_id": "recXXXX" }
    - Lit le coureur
    - Archive ses anciennes séances
    - Crée le nouveau plan version+1
    """
    data = request.get_json(silent=True) or {}
    record_id = data.get("record_id")
    if not record_id:
        return jsonify(error="record_id manquant"), 400

    # 1) Coureur
    coureur_rec = TABLE_COUR.get(record_id)
    if not coureur_rec:
        return jsonify(error="Coureur introuvable"), 404

    cf = coureur_rec.get("fields", {})
    
    # --- 🧮 Quota mensuel (hérité du Groupe) ---
    nb_demandes = cf.get("Nb_plans_mois") or 0
    nb_demandes = int(nb_demandes)

    # Récupération du groupe du coureur
    groupe_ref = cf.get("Groupe")
    if isinstance(groupe_ref, list) and len(groupe_ref) > 0:
        groupe_id = groupe_ref[0]
    elif isinstance(groupe_ref, str):
        groupe_id = groupe_ref
    else:
        groupe_id = None

    # Si aucun groupe → affectation automatique du groupe "Autres"
    if not groupe_id:
        grp_autres = TABLE_GROUPES.first(formula="{Nom du groupe} = 'Autres'")
        if grp_autres:
            groupe_id = grp_autres["id"]
            TABLE_COUR.update(record_id, {"Groupe": [groupe_id]})
        else:
            return jsonify({"error": "❌ Aucun groupe défini et impossible de trouver 'Autres'."})

    # Lecture du quota défini sur le groupe
    groupe = TABLE_GROUPES.get(groupe_id)
    quota = groupe["fields"].get("Quota_mensuel") or 0
    quota = int(quota)

    # Application du quota
    if quota > 0 and nb_demandes >= quota:
        return jsonify({
            "error": "❌ Quota atteint : création de plan non autorisée",
            "message_id": "SC_COACH_QUOTA",
            "nb_demandes": nb_demandes,
            "quota": quota
        })

    # Incrément du compteur (mais sans bloquer si quota = illimité)
    try:
        TABLE_COUR.update(record_id, {"Nb_plans_mois": nb_demandes + 1})
    except:
        pass

    niveau   = first_nonempty(cf, "Niveau", "🧭 Niveau", default="Reprise")
    objectif = first_nonempty(cf, "Objectif", "🎯 Objectif", default="10K")
    phase    = first_nonempty(cf, "Phase", "🏁 Phase", default="Base1")

    # Fréquence cible → depuis table Mapping ou champ direct déjà présent
    freq = int_field(cf, "Fréquence", "Fréquence cible", "Fréquence_cible", default=2)

    # Nb semaines (défaut 8)
    nb_semaines = int_field(cf, "Nb_semaines (calculé)", "Nb_semaines", "Semaines", "Nombre de semaines", default=8)

    # Jours dispo (logique positive)
    jours = jours_dispo(cf)
    nb_jours_min = int_field(cf, "Nb_jours_min", "Nb jours min", default=2)

    if not jours:
        if nb_jours_min == 1:
            # ✅ Message positif → on propose 1 jour cohérent
            jours = ["Dimanche"]
        else:
            # ✅ Cas normal → fallback stable
            jours = ["Mercredi", "Dimanche"]

    # On limite au nombre de séances / semaine (fréquence)
    if len(jours) > freq:
        jours = jours[:freq]

    # Date début plan (dd/mm/yyyy)
    # ✅ On lit la colonne calculée réelle dans Airtable
    start_val = first_nonempty(
    cf,
    "Date début plan (calculée)",
    "Date début plan",
    "📅 Date début plan",
    default=None
)
    date_depart = parse_date_ddmmyyyy(start_val).date()
        
    # Force à ne pas générer des séances dans le passé
    today = datetime.now().date()
    if date_depart < today:
        date_depart = today

    # 🔥 Recalcul automatique si Date objectif existe
    date_obj = cf.get("Date objectif") or cf.get("📅 Date objectif")
    if date_obj:
        date_obj = parse_date_ddmmyyyy(date_obj).date()
        delta_days = (date_obj - date_depart).days
        nb_semaines = max(1, delta_days // 7)
    # ✅ On met à jour la valeur dans Airtable
    try:
        TABLE_COUR.update(record_id, {"Nb_semaines (calculé)": nb_semaines})
    except Exception:
        pass  # on ne bloque pas la génération si la mise à jour échoue

    # 2) Version + Archivage
    version_actuelle = int_field(cf, "Version plan", "Version_plan", default=0)
    nouvelle_version = version_actuelle + 1

    # ✅ Archive même si Version plan = 0
    nb_archives = archive_existing_for_runner(record_id, nouvelle_version - 1)


    # 3) Récup structure (liste ordonnée)
    structure_rows = get_structure_rows(phase)

    if not structure_rows:
        return jsonify(error="Aucune structure trouvée", niveau=niveau, objectif=objectif, phase=phase, frequence=freq), 422

    # 4) Préparer l’échéancier des dates
    slots = generate_dates(date_depart, nb_semaines, jours)
    if not slots:
        return jsonify(error="Aucun slot de date généré"), 422

    # 5) Génération
    created = 0
    previews: List[Dict[str, Any]] = []

    for idx, (week_idx, day_label, date_obj) in enumerate(slots):
        st = structure_rows[idx % len(structure_rows)]
        sf = st.get("fields", {})

        short_type = first_nonempty(sf, "Type séance (court)", "Type seance (court)", "Type seance court")
        phase_row  = first_nonempty(sf, "Phase", default=phase)

        linked_types = sf.get("Séances types") or sf.get("Seances types") or []
        if linked_types and isinstance(linked_types, list):
            ses_type_id = linked_types[0]
            stype = TABLE_SEANCES_TYPES.get(ses_type_id)
        else:
            stype = pick_session_from_type(short_type)

        # --- 🌧️ Cas fallback (pas de modèle trouvé) ---
        if not stype:
            # valeurs fallback stables
            fallback_nom   = short_type or "Footing"
            fallback_cle   = short_type or "EF"
            fallback_duree = 40
            fallback_charge = 1

            payload = {
                "Coureur": [record_id],
                "Nom séance": fallback_nom,
                "Phase": phase_row,
                "Clé séance": fallback_cle,
                "Type séance (court)": short_type or "EF",
                "Durée (min)": fallback_duree,
                "Charge": fallback_charge,
                "Jour planifié": day_label,
                "Date": date_obj.isoformat(),
                "Version plan": nouvelle_version,
                "Semaine": week_idx + 1
            }

            msg_coach = get_message_coach_for(
                phase=phase_row,
                semaine=week_idx + 1,
                niveau=niveau,
                objectif=objectif
            )

            if msg_coach:
                payload["Message coach"] = msg_coach

            msg_week = get_weekly_message(week_idx)

            if msg_week:
                payload["Message hebdo"] = msg_week

            TABLE_SEANCES.create(payload)
            previews.append(payload)
            created += 1
            continue

        # --- 🌞 Cas séance normale (modèle trouvé) ---
        stf = stype.get("fields", {})

        nom_seance = first_nonempty(stf, "Nom séance", "Nom", default=first_nonempty(stf, "Clé séance", "Clé", "Cle", default="Séance"))
        type_court = first_nonempty(stf, "Type séance (court)", "Type seance (court)", "Type seance court", default=short_type or "")
        duree_min  = int_field(stf, "Durée (min)", "Duree (min)", "Durée", default=40)
        charge     = first_nonempty(stf, "Charge", default=None)

        payload = {
            "Coureur": [record_id],
            "Nom séance": nom_seance,
            "Phase": phase_row,
            "Type séance (court)": type_court or "EF",
            "Durée (min)": duree_min,
            "Charge": charge,
            "Jour planifié": day_label,
            "Date": date_obj.isoformat(),
            "Version plan": nouvelle_version,
            "Semaine": week_idx + 1
        }

        cle = first_nonempty(stf, "Clé séance", "Cle séance", "Cle", default=None)
        if cle:
            payload["Clé séance"] = cle

        msg_coach = get_message_coach_for(
            phase=phase_row,
            semaine=week_idx + 1,
            niveau=niveau,
            objectif=objectif
        )
        if msg_coach:
            payload["Message coach"] = msg_coach

        msg_week = get_weekly_message(week_idx)
        if msg_week:
            payload["Message hebdo"] = msg_week

        TABLE_SEANCES.create(payload)
        previews.append(payload)
        created += 1

    # 6) Update version côté coureur
    TABLE_COUR.update(record_id, {"Version plan": nouvelle_version})

    msg = f"✅ Nouveau plan généré — **Version {nouvelle_version}**\n{created} séances créées ({nb_semaines} sem × {len(jours)}/sem)."
    out = {
        "status": "ok",
        "message_id": "SC_COACH_024",
        "message": msg,
        "version_plan": nouvelle_version,
        "nb_semaines": nb_semaines,
        "jours_par_semaine": len(jours),
        "archives": nb_archives,
        "total": created,
        "preview": previews[:min(10, len(previews))]  # petite fenêtre pour contrôle
    }
    return jsonify(out), 200

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)