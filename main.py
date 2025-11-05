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
TABLE_COUR           = get_table("TABLE_COUR"          , "👤 Coureurs", "Coureurs")
TABLE_SEANCES        = get_table("TABLE_SEANCES"       , "🏋️ Séances", "Séances")
TABLE_ARCHIVES       = get_table("TABLE_ARCHIVES"      , "📦 Archives Séances", "Archives Séances", "Archives")
TABLE_SEANCES_TYPES  = get_table("TABLE_SEANCES_TYPES" , "📘 Séances types", "Séances types")
TABLE_STRUCTURE      = get_table("TABLE_STRUCTURE"     , "📐 Structure Séances", "Structure Séances")
TABLE_MAILS          = get_table("TABLE_MAILS"         , "✉️ Mails", "Mails")  # Optionnel, pas utilisé ici

# -----------------------------------------------------------------------------
# Petits helpers
# -----------------------------------------------------------------------------

WEEKDAYS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

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

# -----------------------------------------------------------------------------
# Sélection de structure + pick séance type
# -----------------------------------------------------------------------------

def get_structure_rows(phase: str, niveau: str, objectif: str, frequence: int) -> List[Dict[str, Any]]:
    """
    On cherche dans 📐 Structure Séances les lignes qui matchent :
    - Phase
    - Niveau
    - Objectif
    - Fréquence (si colonne présente ; sinon on l’ignore)
    On renvoie trié par 'Ordre_progression' si dispo.
    """
    # Certaines bases n'ont pas 'Fréquence' en colonne ; on fait un essai "avec" puis fallback "sans"
    formula_with_freq = AND(
        match({"Phase": phase}),
        match({"Niveau": niveau}),
        match({"Objectif": objectif}),
        match({"Fréquence": frequence})
    )
    try:
        rows = TABLE_STRUCTURE.all(formula=formula_with_freq)
    except Exception:
        rows = []

    if not rows:
        # Fallback sans fréquence
        formula_no_freq = AND(
            match({"Phase": phase}),
            match({"Niveau": niveau}),
            match({"Objectif": objectif})
        )
        rows = TABLE_STRUCTURE.all(formula=formula_no_freq)

    # Tri par ordre si présent
    def _order(r):
        f = r.get("fields", {})
        return f.get("Ordre_progression") or f.get("Ordre") or 0
    rows.sort(key=_order)
    return rows

def pick_session_from_type(short_type: str) -> Optional[Dict[str, Any]]:
    """
    Court-circuite si Structure Séances fournit déjà un lien "Séances types".
    Sinon : on cherche dans 📘 Séances types par 'Type séance (court)' == short_type,
    puis on prend la 1ère trouvée, triée par Ordre si dispo.
    """
    if not short_type:
        return None

    # Essai sur le champ 'Type séance (court)' ; fallback 'Type seance court'
    formula = OR_compat(
        match({"Type séance (court)": short_type}),
        match({"Type seance (court)": short_type}),
        match({"Type seance court": short_type}),
        match({"Type séance court": short_type})
    )
    try:
        rows = TABLE_SEANCES_TYPES.all(formula=formula)
    except Exception:
        rows = []

    if not rows:
        return None

    def _ord(r):
        f = r.get("fields", {})
        return f.get("Ordre") or 0
    rows.sort(key=_ord)
    return rows[0]

def OR_compat(*args):
    # petit OR qui fonctionne comme pyairtable.formulas.OR (mais inline)
    # Note : on peut imbriquer les AND/OR via Airtable, ici simplif.
    from pyairtable.formulas import OR
    return OR(*args)

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

    existing = TABLE_SEANCES.all(formula=match({"Coureur": [record_id]}))
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

    niveau   = first_nonempty(cf, "Niveau", "🧭 Niveau", default="Reprise")
    objectif = first_nonempty(cf, "Objectif", "🎯 Objectif", default="10K")
    phase    = first_nonempty(cf, "Phase", "🏁 Phase", default="Base1")

    # Fréquence cible → depuis table Mapping ou champ direct déjà présent
    freq = int_field(cf, "Fréquence", "Fréquence cible", "Fréquence_cible", default=2)

    # Nb semaines (défaut 8)
    nb_semaines = int_field(cf, "Nb_semaines", "Semaines", "Nombre de semaines", default=8)

    # Jours dispo
    jours = jours_dispo(cf)
    if not jours:
        # fallback : 2 jours par défaut (mercredi & dimanche)
        jours = ["Mercredi","Dimanche"]
    # On contraint au nombre de séances / semaine
    if len(jours) > freq:
        jours = jours[:freq]

    # Date début plan (dd/mm/yyyy)
    start_str = first_nonempty(cf, "Date début plan", "Date_debut_plan", "Date début", default=None)
    start_date = parse_date_ddmmyyyy(start_str) if start_str else datetime.now(timezone.utc)

    # 2) Version + Archivage
    version_actuelle = int_field(cf, "Version plan", "Version_plan", default=0)
    nouvelle_version = version_actuelle + 1

    nb_archives = archive_existing_for_runner(record_id, version_actuelle)

    # 3) Récup structure (liste ordonnée)
    structure_rows = get_structure_rows(phase, niveau, objectif, freq)
    if not structure_rows:
        return jsonify(error="Aucune structure trouvée", niveau=niveau, objectif=objectif, phase=phase, frequence=freq), 422

    # 4) Préparer l’échéancier des dates
    slots = generate_dates(start_date, nb_semaines, jours)  # (semaine_idx, jour_label, date_obj)
    if not slots:
        return jsonify(error="Aucun slot de date généré"), 422

    # 5) Génération
    created = 0
    previews: List[Dict[str, Any]] = []

    # On duplique la structure sur l'horizon temporel : ex. 2 jours/sem → on répète
    # structure_rows[i % len(structure_rows)] sert d'alternance basique et stable.
    for idx, (week_idx, day_label, date_obj) in enumerate(slots):
        st = structure_rows[idx % len(structure_rows)]
        sf = st.get("fields", {})

        short_type = first_nonempty(sf, "Type séance (court)", "Type seance (court)", "Type seance court")
        phase_row  = first_nonempty(sf, "Phase", default=phase)

        # Si la structure référence directement une ou plusieurs "Séances types", on les prend en priorité.
        linked_types = sf.get("Séances types") or sf.get("Seances types") or []
        if linked_types and isinstance(linked_types, list):
            # On prend la première séance liée
            ses_type_id = linked_types[0]
            stype = TABLE_SEANCES_TYPES.get(ses_type_id)
        else:
            stype = pick_session_from_type(short_type)

        if not stype:
            # si rien trouvé, on crée une séance générique EF 40' comme fallback minimal
            nom = f"{short_type or 'EF'} – fallback 40'"
            payload = {
                "Coureur": [record_id],
                "Nom séance": nom,
                "Type séance": short_type or "EF",
                "Type séance (court)": short_type or "EF",
                "Phase": phase_row,
                "Durée (min)": 40,
                "Charge": 1,
                "Jour planifié": day_label,
                "Date": date_obj.date().isoformat(),
                "Version plan": nouvelle_version
            }
            TABLE_SEANCES.create(payload)
            previews.append(payload)
            created += 1
            continue

        stf = stype.get("fields", {})
        # Extraction des champs utiles depuis 📘 Séances types
        nom_seance   = first_nonempty(stf, "Nom séance", "Nom", default=first_nonempty(stf, "Clé séance", "Clé", "Cle", default="Séance"))
        type_full    = first_nonempty(stf, "Type séance", "Type seance", default="")
        type_court   = first_nonempty(stf, "Type séance (court)", "Type seance (court)", "Type seance court", default=short_type or "")
        duree_min    = int_field(stf, "Durée (min)", "Duree (min)", "Durée", default=40)
        charge       = first_nonempty(stf, "Charge", default=None)

        payload = {
            "Coureur": [record_id],
            "Nom séance": nom_seance,
            "Type séance": type_full or type_court or "EF",
            "Type séance (court)": type_court or "EF",
            "Phase": phase_row,
            "Durée (min)": duree_min,
            "Charge": charge,
            "Jour planifié": day_label,
            "Date": date_obj.date().isoformat(),
            "Version plan": nouvelle_version
        }
        # Optionnel : garder trace de la clé séance si dispo
        cle = first_nonempty(stf, "Clé séance", "Cle séance", "Cle", default=None)
        if cle:
            payload["Clé séance"] = cle

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
    port = int(_env("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)