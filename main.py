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

import os
import re
import sys
import math
import json
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any, Optional, Tuple

from flask import Flask, request, jsonify
from pyairtable import Table

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

    last_err = None
    for fb in fallback_names:
        try:
            return Table(AIRTABLE_KEY, BASE_ID, fb)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError(f"Impossible d'ouvrir la table {env_name}")

# Tables (avec libellés FR compatibles)
TABLE_COUR                  = get_table("TABLE_COUR"                    , "👤 Coureurs", "Coureurs")
TABLE_SEANCES               = get_table("TABLE_SEANCES"                 , "🏋️ Séances", "Séances")
TABLE_ARCHIVES              = get_table("TABLE_ARCHIVES"                , "📦 Archives Séances", "Archives Séances", "Archives")
TABLE_SEANCES_TYPES         = get_table("TABLE_SEANCES_TYPES"           , "📘 Séances types", "Séances types")
TABLE_STRUCTURE             = get_table("TABLE_STRUCTURE"               , "📐 Structure Séances", "Structure Séances")
TABLE_MAILS                 = get_table("TABLE_MAILS"                   , "✉️ Mails", "Mails")  # Optionnel, non utilisé ici
TABLE_MESSAGES_SMARTCOACH   = get_table("TABLE_MESSAGES_SMARTCOACH"     , "🗂️ Messages SmartCoach", "Messages SmartCoach")
TABLE_VDOT_REF              = get_table("TABLE_VDOT_REF"                , "VDOT_References", "VDOT Reference", "VDOT")
# -----------------------------------------------------------------------------
# Petits helpers (parsing, mapping, etc.)
# -----------------------------------------------------------------------------

WEEKDAYS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
DAY_ORDER   = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]

WEEKDAY_MAP = {
    "Lundi": 0, "Mardi": 1, "Mercredi": 2, "Jeudi": 3,
    "Vendredi": 4, "Samedi": 5, "Dimanche": 6,
}

def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def parse_date_ddmmyyyy(value: Any) -> datetime:
    """
    Gère automatiquement :
    - dd/mm/yyyy (format formulaire)
    - yyyy-mm-dd (format Airtable natif)
    - datetime/date déjà parsée
    - fallback = aujourd’hui UTC
    """
    if not value:
        return datetime.now(timezone.utc)

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    s = str(value).strip()

    # Format ISO / Airtable → yyyy-mm-dd
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            y, m, d = s.split("-")
            return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
        except Exception:
            pass

    # Format dd/mm/yyyy
    if "/" in s:
        try:
            d, m, y = s.split("/")
            return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
        except Exception:
            pass

    # Fallback robuste
    return datetime.now(timezone.utc)

def parse_start_date(val) -> date:
    """
    Accepte :
    - objet date/datetime venant d'Airtable
    - string "YYYY-MM-DD"
    - string "DD/MM/YYYY"
    Retourne datetime.date (avec fallback = aujourd’hui)
    """
    if not val:
        return datetime.now().date()

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    s = str(val).strip()
    # ISO
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        pass
    # dd/mm/yyyy
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        return datetime.now().date()

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

def jours_dispo(cf: Dict[str, Any]) -> List[str]:
    """
    Retourne une liste de jours (strings)
    Fonctionne même si le champ est multi-select (liste) ou texte comma-separated.
    """
    raw = cf.get("Jours disponibles") or cf.get("📅 Jours disponibles")
    if not raw:
        return []
    if isinstance(raw, list):
        return [j for j in raw if j]
    return [j.strip() for j in str(raw).replace(",", " ").split() if j.strip()]

def weekday_from_fr(d: str) -> int:
    return WEEKDAY_MAP.get(d, 0)

def first_occurrence_on_or_after(start: date, target_weekday: int) -> date:
    delta = (target_weekday - start.weekday()) % 7
    return start + timedelta(days=delta)

def generate_dates(date_depart, nb_semaines, jours):
    slots = []
    current_date = date_depart

    for w in range(nb_semaines):
        for j in jours:
            # ✅ calcule la date réelle du jour demandé
            target_weekday = WEEKDAY_MAP.get(j, 0)
            d = current_date + timedelta(days=(target_weekday - current_date.weekday()) % 7)

            slots.append({
                "date": d,
                "semaine": w + 1,
                "jour": j,
                "last_week": (w == nb_semaines - 1)
            })

        # ✅ semaine suivante
        current_date += timedelta(days=7)

    return slots

def get_vdot_paces(vdot: int) -> dict:
    """Retourne les allures du coureur (E, M, T, I, R) depuis Airtable."""
    rows = TABLE_VDOT_REF.all(formula=f"{'{VDOT}'} = {vdot}")
    if not rows:
        return {}
    rec = rows[0]["fields"]
    return {
        "E": rec.get("Sec_E"),
        "M": rec.get("Sec_M"),
        "T": rec.get("Sec_T"),
        "I": rec.get("Sec_I"),
        "R": rec.get("Sec_R"),
    }

def build_race_strategy(vdot: int, distance_km: int = 10) -> str:
    paces = get_vdot_paces(vdot)
    if not paces or not paces.get("M"):
        return "Course plaisir : pars cool, stabilise, finis en maîtrise ✨"

    sec_per_km = paces["M"]
    minutes = sec_per_km // 60
    seconds = sec_per_km % 60
    pace_str = f"{minutes}:{seconds:02d}/km"

    return (
        f"🎯 **Stratégie 10 km**\n"
        f"- Départ contrôlé 2 km → {pace_str} + 5 à 8 sec/km\n"
        f"- Du km 3 au km 8 → stabilise à **{pace_str}**\n"
        f"- Km 9-10 → si tu as du jus → accélère progressivement 💥\n"
        f"\nSouffle long, épaules basses, relâche max. Tu es prêt(e)."
    )

def get_modele_seance_race(mode: str, objectif: str):
    """
    Récupère en base la séance VEILLE et RACE_DAY correspondant à l'objectif.
    Exemples de clés recherchées :
        VEILLE_10K, RACE_DAY_10K
        VEILLE_SEMI, RACE_DAY_MARATHON
    """
    if not objectif:
        return None, None

    cle_race = f"RACE_DAY_{objectif.upper()}"
    cle_veille = f"VEILLE_{objectif.upper()}"

    # Recherche des séances modèles dans Types Séances
    recs = TABLE_TYPES_SEANCES.all()

    veille = next((r.get("fields") for r in recs
                   if r["fields"].get("Type séance (court)") == cle_veille
                   and r["fields"].get("Mode") == mode), None)

    race = next((r.get("fields") for r in recs
                 if r["fields"].get("Type séance (court)") == cle_race
                 and r["fields"].get("Mode") == mode), None)

    return veille, race

# -----------------------------------------------------------------------------
# Messages hebdo (optionnel)
# -----------------------------------------------------------------------------

def get_weekly_message(semaine_index_0: int) -> str:
    """
    S1->M1, S2->M2, S3->M3, S4->M4, S5->M1, etc.
    On s’appuie sur la table 🗂️ Messages SmartCoach avec un champ ID_Message ∈ {M1..M4}
    """
    code = f"M{((semaine_index_0) % 4) + 1}"  # semaine_index_0 = 0..N-1
    row = TABLE_MESSAGES_SMARTCOACH.first(formula=f"{{ID_Message}} = '{code}'")
    if not row:
        return ""
    fields = row.get("fields", {})
    return fields.get("Message (template)", "") or fields.get("Message", "") or ""

# -----------------------------------------------------------------------------
# Archivage – robuste et verbeux
# -----------------------------------------------------------------------------

def normalize_for_json(data):
    """
    Convertit proprement un dict Airtable en dict JSON-sérialisable :
    - sets → list
    - datetime/date → isoformat
    - objets complexes → string
    """
    if isinstance(data, dict):
        return {k: normalize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [normalize_for_json(x) for x in data]
    if isinstance(data, set):
        return list(data)
    if isinstance(data, datetime):
        return to_utc_iso(data)
    if isinstance(data, date):
        return data.isoformat()
    return data

def normalize_seance_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Version nettoyée & stable des champs d'une séance,
    prête à être archivée ou sérialisée.
    """
    return {
        "Clé séance":               fields.get("Clé séance"),
        "Coureur":                  fields.get("Coureur", []),
        "Nom séance":               fields.get("Nom séance"),
        "Phase":                    fields.get("Phase"),
        "Type séance (court)":      fields.get("Type séance (court)"),
        "Type séance":              fields.get("Type séance"),
        "Durée (min)":              fields.get("Durée (min)"),
        "Semaine":                  fields.get("Semaine"),
        "Jour planifié":            fields.get("Jour planifié"),
        "Charge":                   fields.get("Charge"),
        "Version plan":             fields.get("Version plan"),
        "Date":                     fields.get("Date"),
        "Message coach":            fields.get("Message coach"),
        "Message hebdo":            fields.get("Message hebdo"),
        "Allure / zone":            fields.get("Allure / zone"),
        "Source":                   fields.get("Source"),
    }

def _create_archive_row(payload_base: Dict[str, Any]) -> None:
    """
    Crée une ligne dans la table Archives en essayant 2 noms possibles pour l'ID,
    afin d’être tolérant aux intitulés (avec/sans emoji).
    """
    id_variants = ["🆔 ID Séance Originale", "ID séance originale"]
    last_exc = None
    for field_name in id_variants:
        p = payload_base.copy()
        # remap la clé d’ID vers le nom essayé
        p[field_name] = p.pop("__ID_SEANCE_ORIG__", None)
        try:
            TABLE_ARCHIVES.create(p)
            return
        except Exception as e:
            last_exc = e
    if last_exc:
        raise last_exc

def archive_existing_for_runner(record_id: str, version_reference: int) -> int:
    """
    Archive toutes les séances du coureur dont la Version plan est différente
    de la version de référence (version du coureur au moment T).
    """
    if not record_id:
        return 0

    print(f"[ARCHIVE] Coureur = {record_id}, Version de référence = {version_reference}")

    # 1) Récupération des séances du coureur (champ lien 'Coureur')
    records = TABLE_SEANCES.all(
        formula=f"SEARCH('{record_id}', ARRAYJOIN({{Coureur}}, ','))"
    )
    print(f"[ARCHIVE] Séances trouvées = {len(records)}")

    # 2) Filtrer celles à archiver (≠ version_reference)
    to_archive = []
    for r in records:
        fields = r.get("fields", {})
        v = fields.get("Version plan") or fields.get("Version_plan") or 0
        try:
            v = int(v)
        except Exception:
            v = 0

        print(f" - {r['id']} → Version={v}")
        if v != version_reference:
            to_archive.append((r, v))

    if not to_archive:
        print("[ARCHIVE] Aucun archivage nécessaire ✅")
        return 0

    print(f"[ARCHIVE] → {len(to_archive)} séances à archiver")

    now_iso = to_utc_iso(datetime.now(timezone.utc))
    archived_count = 0

    for rec, v in to_archive:
        champs = rec.get("fields", {})
        try:
            data = normalize_seance_fields(champs)
            champs_json = json.dumps(normalize_for_json(data), ensure_ascii=False)

            payload = {
                "__ID_SEANCE_ORIG__": rec.get("id"),  # clé temporaire pour mappage tolérant
                "Coureur": [record_id],
                "Nom séance": data.get("Nom séance"),
                "Clé séance": data.get("Clé séance"),
                "Type séance": data.get("Type séance"),
                "Type séance (court)": data.get("Type séance (court)"),
                "Phase": data.get("Phase"),
                "Durée (min)": data.get("Durée (min)"),
                "Charge": data.get("Charge"),
                "Allure / zone": data.get("Allure / zone"),
                "Version plan": v,
                "Date archivage": data.get("Date"),
                "Détails JSON": champs_json,
                "Date archivage": now_iso,
                "Source": "auto-archive",
            }

            _create_archive_row(payload)
            TABLE_SEANCES.delete(rec["id"])
            archived_count += 1
            print(f"[ARCHIVE] ✅ Archivé & supprimé → {rec.get('id')}")

        except Exception as e:
            print(f"[ARCHIVE] ❌ Erreur archivage {rec['id']}: {e}")

    print(f"[ARCHIVE] Terminé → {archived_count} séances archivées ✅")
    return archived_count

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
    
# ------------------------------------------------------------------------------
# Récupération d'allure depuis table VDOT_References (propre)
# ------------------------------------------------------------------------------
def get_pace_from_vdot(vdot: int, zone: str) -> str:
    """
    zone ∈ {"E","M","T","I","R"}
    Retourne min/km (ex: "5:12")
    """
    recs = TABLE_VDOT_REF.all(formula=f"{{VDOT}} = {vdot} AND {{Zone}} = '{zone}'")
    if not recs:
        return "Allure non définie"
    f = recs[0]["fields"]
    return f.get("Allure (min/km)", f.get("Allure", "N/A"))
    
#------------------------------------------------------------------------------
# STRATEGIE DE COURSE
#------------------------------------------------------------------------------
def build_race_strategy(vdot, distance_km):
    # On utilise l’allure "M" comme base 10K (plus réaliste que T pour la course)
    try:
        allure_cible = get_pace_from_vdot(vdot, "M")
    except:
        allure_cible = "Allure confortable + contrôle"

    return f"""
🎯 Objectif : {distance_km} km
Allure cible : {allure_cible} / km

✅ Stratégie :
- 0 → 2 km : Calme, tu poses la respiration.
- 2 → 7 km : Stabilité. Régulier. Économie de geste.
- 7 → 9 km : Tu réveilles le moteur, relâchement + fréquence.
- Dernier km : Tu donnes ce qu'il reste, sans crispation.

💡 Conseil :
Le plus gros piège → partir trop vite.
Viser **contrôle + relâchement** sur les 2 premiers kilomètres.
"""

# -----------------------------------------------------------------------------
# Endpoint principal
# -----------------------------------------------------------------------------

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    """
    JSON attendu : { "record_id": "recXXXXXXXX" }
    - Lit le coureur
    - Met à jour Version plan (Version+1)
    - Archive les anciennes séances (≠ version courante)
    - Génère un nouveau plan
    """
    data = request.get_json(silent=True) or {}
    record_id = data.get("record_id")
    if not record_id:
        return jsonify(error="record_id manquant"), 400

    # --- 1) Lecture du coureur ---
    coureur_rec = TABLE_COUR.get(record_id)
    if not coureur_rec:
        return jsonify(error="Coureur introuvable"), 404
    cf = coureur_rec.get("fields", {})

    # --- Nb demandes / mois ---
    nb_demandes = int_field(cf, "Nb_plans_mois", default=0)
    try:
        TABLE_COUR.update(record_id, {"Nb_plans_mois": nb_demandes + 1})
    except Exception as e:
        print(f"[WARN] Maj Nb_plans_mois: {e}")

    # --- Paramètres principaux ---
    niveau   = first_nonempty(cf, "Niveau", "🧭 Niveau", default="Reprise")
    objectif = first_nonempty(cf, "Objectif", "🎯 Objectif", default="10K")
    phase    = first_nonempty(cf, "Phase", "🏁 Phase", default="Prépa générale")
    # VDOT utilisé pour calculer les allures et la stratégie de course
    vdot = int_field(cf, "VDOT_cible", "VDOT", default=45)

    # Fréquence cible (séances/semaine)
    freq = int_field(cf, "Fréquence", "Fréquence cible", "Fréquence_cible", default=2)

    # --- Jours choisis par l'utilisateur ---
    jours = (jours_dispo(cf) or [])
    # Ordonner de façon stable
    ORDER_JOURS = DAY_ORDER
    jours = sorted(jours, key=lambda j: ORDER_JOURS.index(j) if j in ORDER_JOURS else 99)

    nb_jours_min = int_field(cf, "Nb_jours_min", "Nb jours min", default=2)
    if not jours:
        jours = ["Dimanche"] if nb_jours_min == 1 else ["Mercredi", "Dimanche"]

    # Limiter au volume de la fréquence
    if len(jours) > freq:
        jours = jours[:freq]

    # --- Dates : départ & objectif ---
    start_val  = first_nonempty(cf, "Date début plan (calculée)", "Date début plan", "📅 Date début plan", default=None)
    date_depart = parse_start_date(start_val)

    obj_val   = first_nonempty(cf, "Date objectif", "📅 Date objectif", default=None)
    date_obj  = parse_date_ddmmyyyy(obj_val).date() if obj_val else None

    # --- Calcul du nombre de semaines basé sur la table Coureurs ---
    nb_sem_total = int_field(cf, "Nb_sem_total", default=8)  # ← ton champ maître
    nb_semaines = nb_sem_total

    # On ajoute systématiquement la dernière semaine de course si date_obj existe
    add_race_week = bool(date_obj)

    print(f"[GEN] start={date_depart} obj={date_obj} nb_semaines={nb_semaines} jours={jours}")

    # --- 2) Version + Archivage ---
    version_actuelle = int_field(cf, "Version plan", "Version_plan", default=0)
    nouvelle_version = version_actuelle + 1

    # Mise à jour de la version du coureur AVANT l’archivage
    TABLE_COUR.update(record_id, {"Version plan": nouvelle_version})

    # Archivage de tout ce qui n'a pas la version courante (nouvelle_version)
    nb_archives = archive_existing_for_runner(record_id, nouvelle_version)
    print(f"[ARCHIVE] → {nb_archives} séances archivées (ancienne version = {version_actuelle}, nouvelle = {nouvelle_version})")

    # --- 3) Structure des séances ---
    # Phase "Base1/Base2" mappée vers "Prépa générale"
    phase_lookup = "Prépa générale" if phase in ("Base1", "Base2") else phase
    rows = TABLE_STRUCTURE.all(formula=f"{{Phase}} = '{phase_lookup}'")
    if not rows:
        return jsonify(error="Aucune structure trouvée", phase=phase_lookup), 422
    structure_rows = sorted(rows, key=lambda r: r.get("fields", {}).get("Ordre", 0))

    # --- 4) Génération des dates des séances ---
    slots = generate_dates(date_depart, nb_semaines, jours)
    if not slots:
        return jsonify(error="Aucun slot de date généré"), 422

    # --- 5) Création des séances ---
    previews = []
    created = 0

    for idx, s in enumerate(slots):
        week_idx = s["semaine"]
        day_label = s["jour"]
        date_slot = s["date"]

        # On détectera la dernière semaine ainsi :
        last_week = s.get("last_week", False)

        st = structure_rows[idx % len(structure_rows)]
        sf = st.get("fields", {})

        short_type = first_nonempty(sf, "Type séance (court)", "Type seance (court)", "Type seance court", default="EF")
        phase_row  = first_nonempty(sf, "Phase", default=phase_lookup)

        linked_types = sf.get("Séances types") or sf.get("Seances types") or []
        if linked_types:
            stype = TABLE_SEANCES_TYPES.get(linked_types[0])
        else:
            # Fallback par clé courte
            records = TABLE_SEANCES_TYPES.all(formula=f"{{Type séance (court)}} = '{short_type}'")
            stype = records[0] if records else None

        if not stype:
            # Fallback minimal
            payload = {
                "Coureur": [record_id],
                "Nom séance": short_type or "Footing",
                "Phase": phase_row,
                "Clé séance": short_type or "EF",
                "Type séance (court)": short_type or "EF",
                "Durée (min)": 40,
                "Charge": 1,
                "Jour planifié": day_label,
                "Date": date_slot.isoformat(),
                "Version plan": nouvelle_version,
                "Semaine": (week_idx + 1),
                "Message coach": "Reste fluide et régulier, sans forcer."
            }
        else:
            stf = stype.get("fields", {})
            payload = {
                "Coureur": [record_id],
                "Nom séance": first_nonempty(stf, "Nom séance", "Nom", default="Séance"),
                "Phase": phase_row,
                "Type séance (court)": first_nonempty(stf, "Type séance (court)", default=short_type),
                "Durée (min)": int_field(stf, "Durée (min)", default=40),
                "Charge": first_nonempty(stf, "Charge", default=None),
                "Jour planifié": day_label,
                "Date": date_slot.isoformat(),
                "Version plan": nouvelle_version,
                "Semaine": week_idx + 1
            }
            cle = first_nonempty(stf, "Clé séance", "Cle séance", "Cle")
            if cle:
                payload["Clé séance"] = cle
            msg_coach = first_nonempty(stf, "Message_coach (modèle)", "Message coach", "Message_coach", default=None)
            if msg_coach:
                payload["Message coach"] = msg_coach

        msg_week = get_weekly_message(week_idx)
        if msg_week:
            payload["Message hebdo"] = msg_week

        # --- Injection automatique dernière semaine : VEILLE + RACE_DAY ---
        mode = mode_normalise  # déjà déterminé
        objectif = objectif_normalise  # ex: "10K", "SEMI", "MARATHON"

        veille, course = get_modele_seance_race(mode, objectif)

        if veille and course and nb_semaines > 1:
            # On modifie la semaine finale (nb_semaines - 1)
            semaine_finale = nb_semaines

            # VEILLE = jour disponible juste avant RACE
            # On place la course sur le dernier jour dispo
            last_day = jours[-1]
            veille_day = jours[-2] if len(jours) > 1 else jours[-1]

            # On ajoute / remplace dans le plan
            plan = [p for p in plan if p["Semaine"] < semaine_finale]

            plan.append({
                **course,
                "Coureur": [record_id],
                "Semaine": semaine_finale,
                "Jour planifié": last_day,
                "Type séance (court)": course.get("Type séance (court)"),
                "Version plan": version_plan,
            })

            plan.append({
                **veille,
                "Coureur": [record_id],
                "Semaine": semaine_finale,
                "Jour planifié": veille_day,
                "Type séance (court)": veille.get("Type séance (court)"),
                "Version plan": version_plan,
            })


        TABLE_SEANCES.create(payload)
        previews.append(payload)
        created += 1

    # --- Ajout final de la semaine de course ---
    if date_obj:
    # 1) veille
    veille = date_obj - timedelta(days=1)
    TABLE_SEANCES.create({
        "Coureur": [record_id],
        "Nom séance": "📦 Veille de course — Relax + Réassurance",
        "Clé séance": "VEILLE",
        "Type séance (court)": "VEILLE",
        "Phase": "Compétition",
        "Semaine": nb_semaines,
        "Jour planifié": veille.strftime("%A"),
        "Date": veille.isoformat(),
        "Version plan": nouvelle_version,
        "Message coach": "15-20 min très facile + 3 lignes droites relâchées. On respire."
    })

    # 2) COURSE — 10 KM
    TABLE_SEANCES.create({
        "Coureur": [record_id],
        "Nom séance": "🏁 Jour de course — 10 km",
        "Clé séance": "RACE_DAY_10K",
        "Type séance (court)": "COURSE",
        "Phase": "Compétition",
        "Semaine": nb_semaines,
        "Jour planifié": date_obj.strftime("%A"),
        "Date": date_obj.isoformat(),
        "Version plan": nouvelle_version,
        "Message coach": build_race_strategy(vdot, 10),
        "Message hebdo": "Aujourd’hui tu t’exprimes. Tu as tout construit pour ça."
    })


    # --- 6) Remise de la version (sécurité idempotence) ---
    try:
        TABLE_COUR.update(record_id, {"Version plan": nouvelle_version})
    except Exception as e:
        print(f"[WARN] Maj Version plan finale: {e}")

    msg = f"✅ Nouveau plan généré — **Version {nouvelle_version}**\n{created} séances créées ({nb_semaines} sem × {len(jours)}/sem)."
    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_021",
        "message": msg,
        "version_plan": nouvelle_version,
        "nb_semaines": nb_semaines,
        "jours_par_semaine": len(jours),
        "archives": nb_archives,
        "total": created,
        "preview": previews
    }), 200

# -----------------------------------------------------------------------------
# Debug version hash
# -----------------------------------------------------------------------------

import hashlib
import inspect

@app.get("/_debug/version")
def debug_version():
    try:
        source = inspect.getsource(sys.modules[__name__])
    except Exception:
        source = "no-source"
    h = hashlib.sha1(source.encode()).hexdigest()[:10]
    return {"status": "running", "file_hash": h}

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=port)