# smartcoach_core/airtable_fields.py
# =====================================================
# Référentiel CENTRALISÉ des champs Airtable
# Source unique de vérité pour les accès aux données
# =====================================================

class ATFIELDS:
    """
    Référentiel des champs Airtable.
    Convention :
    - préfixe COU_ pour la table Coureurs
    - nom Python normalisé
    - valeur = nom EXACT du champ Airtable (emoji inclus)
    """

    # =================================================
    # 👟 TABLE : COUREURS
    # =================================================

    COU_RECORD_ID = "Record ID"
    COU_PRENOM = "Prénom"
    COU_EMAIL = "Email"
    COU_GENRE = "Genre"
    COU_AGE = "Âge"

    COU_CAP_CHOISI = "🎯 Cap choisi"
    COU_OBJECTIF_CHRONO = "⏱️ Objectif_chrono_fmt"

    COU_DATE_DEBUT_PLAN = "Date début plan (calculée)"
    COU_DATE_COURSE = "date_course"
    COU_DUREE_PLAN_CALC = "Durée_plan_calculée_sem"
    COU_TEST_DUREE_PLAN = "Test_duree_plan"

    COU_NIVEAU = "Niveau"
    COU_NIVEAU_NORMALISE = "Niveau_normalisé"
    COU_OBJECTIF_NORMALISE = "Objectif_normalisé"
    COU_MODE = "Mode"
    COU_CLE_NIVEAU_REF = "Clé_niveau_reference"

    COU_JOURS_DISPO = "Jours disponibles"
    COU_NB_JOURS_DISPO = "📅 Nb_jours_dispo"
    COU_JOURS_FINAL = "📅 Jours_final"
    COU_NB_JOURS_FINAL = "📅 Nb_jours_final"

    COU_SEANCES_3 = "🏋️ Séances 3"

    COU_QUOTA_MENSUEL = "Quota mensuel"
    COU_DROIT_GENERATION = "Droit génération plan ?"

    COU_VERSION_PLAN = "Version plan"
    COU_VERSION_PLAN_M1 = "Version plan M-1"

    # =================================================
    # ⚖️ TABLE : RÉFÉRENCE JOURS
    # =================================================

    RJ_MODE = "Mode"
    RJ_NIVEAU = "Niveau"
    RJ_OBJECTIF = "Objectif"

    # Clé_niveau_reference déjà déclarée dans la section Coureurs :
    # COU_CLE_NIVEAU_REF = "Clé_niveau_reference"

    RJ_NB_JOURS_MIN = "Nb_jours_min"
    RJ_NB_JOURS_MAX = "Nb_jours_max"
    RJ_ESPACEMENT_MIN = "espacement_min"
    RJ_ESPACEMENT_MAX = "espacement_max"
    RJ_JOURS_PROPOSES = "Jours_proposés"
    RJ_COMMENTAIRE_COACH = "Commentaire coach"

    # Relation
    RJ_COUREURS_LINK = "👤 Coureurs"

    # =================================================
    # 📋 TABLE : SUIVI GÉNÉRATION
    # =================================================

    SG_LOG_ID = "Nom du log / Record ID"

    SG_DATE_GENERATION = "Date de génération"
    
    SG_TYPE_SCENARIO = "Type de scénario"
    SG_SOURCE = "Source"
    SG_STATUT_EXECUTION = "Statut exécution"
    SG_MESSAGE_STATUT = "Message de statut"
    SG_ERREUR_CODE = "Erreur_Code"
    SG_DUREE_EXECUTION = "Durée exécution (s)"
    SG_DEBUG_ACTIF = "Debug actif ?"
    SG_VERSION_SCRIPT = "Version script"

    SG_PLAN_GENERE = "Plan généré ?"
    SG_NOM_PLAN = "Nom du plan (lookup)"  # lookup

    SG_NB_SEANCES_GENEREES = "Nb séances générées"
    SG_EMAIL_ENVOYE = "Email envoyé ?"

    SG_TYPE_PLAN = "Type de plan"
    SG_DUREE_PLAN_SEMAINES = "Durée totale plan (semaines)"
    SG_ALERTES_RENCONTREES = "Alertes rencontrées"

    SG_MAKE_ROUTE_NAME = "Nom de la route Make"
    SG_CLE_DIAGNOSTIC = "Clé de diagnostic"

    SG_LIEN_JSON_BRUT = "Lien JSON brut"

    SG_ENVIRONNEMENT = "Environnement"

    # =================================================
    # 🏋️ TABLE : SÉANCES
    # =================================================

    SEANCE_NOM = "Nom séance"
    SEANCE_ID = "ID séance (clé)"                 # Clé métier stable
    SEANCE_TYPE = "Type de séance"
    SEANCE_PHASE = "Phase"
    SEANCE_JOUR_RELATIF = "Jour relatif"
    SEANCE_DATE_PREVUE = "Date prévue"

    SEANCE_COUREUR_LINK = "Coureur"              # lookup
    SEANCE_MODE = "Mode"
    SEANCE_OBJECTIF_LINK = "Objectif"            # lookup
    SEANCE_SEMAINE = "Semaine"

    SEANCE_SEANCES_TYPES_LINK = "Séances types"  # lien vers modèle
    SEANCE_NIVEAU = "Niveau"
    SEANCE_PLAN_ASSOCIE = "Plan associé"

    SEANCE_OBJECTIF_SEANCE = "Objectif_seance"

    SEANCE_TYPE_ALLURE = "Type d’allure"
    SEANCE_ALLURE_CIBLE = "Allure cible (min/km)"
    SEANCE_VITESSE_CIBLE = "Vitesse cible (km/h)"
    SEANCE_CHARGE = "Charge"
    SEANCE_ZONE_CARDIO = "Zone cardio estimée"

    SEANCE_DESCRIPTION = "Description"
    SEANCE_CONSEIL = "Conseil du coach"
    SEANCE_MATERIEL = "Matériel requis"
    SEANCE_LIEU = "Lieu conseillé"

    SEANCE_REF_CATEGORIE_LINK = "Lien vers Référentiel Catégories Séances"
    SEANCE_PHASES_LOOKUP = "Phases"
    SEANCE_LINKED_SESSION_TYPES = "Linked_Session_Types"

    SEANCE_CLE_INTERNE = "Clé interne calculée"
    SEANCE_DATE_JSON = "Date JSON (format ISO)"

    SEANCE_RECORD_ID = "Record ID"
    SEANCE_NOM_ROUTE = "Nom de la route (Make)"

    # ⚠️ Ne pas redéclarer ENVIRONNEMENT ici
    # Utiliser ATFIELDS.ENVIRONNEMENT (déjà déclaré une seule fois)

    # ============================================================
    # TABLE : SÉANCES TYPES  (Structure officielle SmartCoach 2025)
    # ============================================================

    # ░░ Identification générale
    STYPE_NOM = "Nom de la séance type"               # label métier
    STYPE_ID = "ID type (clé)"                        # identifiant unique Airtable
    STYPE_CLE_SEANCE = "Clé séance"                   # clé courte technique (ex: AS10_REC)

    # ░░ Classification / Filtrage
    STYPE_MODE = "Mode"                               # Running / Vitalité / Kids / Hyrox
    STYPE_PHASE_CIBLE = "Phase cible"                 # Base1 / Base2 / Progression / Affûtage / Course
    STYPE_CATEGORIE = "Catégorie"                     # Endurance, VMA, Seuil, etc.
    STYPE_CLE_TECHNIQUE = "Clé technique complète"    # clé métier (ex: "Affûtage-Seuil-T")
    STYPE_CAT_SMARTCOACH = "🔑 Catégorie SmartCoach"   # mapping interne SC

    # ░░ Paramètres athlète
    STYPE_NIVEAU = "Niveau"                           # Débutant / Reprise / Confirmé

    # ░░ Intensité & Durées
    STYPE_DUREE = "Durée (min)"                       # durée totale (min)
    STYPE_DUREE_MOY = "Durée moyenne (min)"           # parfois présent → alias
    STYPE_REPETITIONS = "Répétitions"                 # nb reps si applicable
    STYPE_RECUP = "Récupération (sec)"                # temps récup total/répétition

    # ░░ Allures & VDOT
    STYPE_TYPE_ALLURE = "Type d’allure"               # E / M / T / I / R
    STYPE_TYPE_ALLURE_2 = "Type d’allure 2"           # champ secondaire
    STYPE_VDOT_MIN = "VDOT_min"
    STYPE_VDOT_MAX = "VDOT_max"

    # ░░ Distances
    STYPE_DISTANCE_MOY = "Distance moyenne (km)"

    # ░░ Description & affichage
    STYPE_DESCRIPTION = "Description"                 # description texte coach
    STYPE_CONSEIL_COACH = "Conseil du coach"          # phrase motivante
    STYPE_VIDEO = "Vidéo / illustration"              # URL / fichier
    STYPE_MATERIEL = "Matériel requis"                # Montre, dossard, rien…
    STYPE_ENVIRONNEMENT = "Environnement conseillé"   # Piste / extérieur / parc…

    # ░░ Fonctions avancées
    STYPE_TYPE_SEANCE_COURT = "Type séance (court)"   # code abrégé
    STYPE_FREQUENCE_CIBLE = "Fréquence cible"         # mapping fréquence/sem
    STYPE_MAPPING_FREQUENCE = "Mapping Fréquence"     # table secondaire

    # ░░ Modes optionnels
    STYPE_KIDS = "Kids"                               # oui/non
    STYPE_VITALITE = "Vitalité"                       # oui/non
    STYPE_HYROX_DEKA = "Hyrox/DEKA"                   # oui/non

    # ░░ Versionning
    STYPE_VERSION_MODELE = "Version modèle"


    # =================================================
    # ⚖️ TABLE : VDOT_REFERENCE
    # =================================================

    VDOT_VDOT = "VDOT"
    VDOT_EQUIVALENT_NIVEAU = "Niveau équivalent"
    VDOT_VERSION_SOURCE = "Version source"
    VDOT_GROUPE_ALLURES = "Groupe d’allures"

    # --- Allures min/km ---
    VDOT_ALLURE_E = "Allure_E (min/km)"
    VDOT_ALLURE_M = "Allure_M (min/km)"
    VDOT_ALLURE_T = "Allure_T (min/km)"
    VDOT_ALLURE_I = "Allure_I (min/km)"
    VDOT_ALLURE_R = "Allure_R (min/km)"

    # --- Vitesses km/h ---
    VDOT_VITESSE_E = "Vitesse_E (km/h)"
    VDOT_VITESSE_M = "Vitesse_M (km/h)"
    VDOT_VITESSE_T = "Vitesse_T (km/h)"
    VDOT_VITESSE_I = "Vitesse_I (km/h)"
    VDOT_VITESSE_R = "Vitesse_R (km/h)"

    # --- Charges ---
    VDOT_CHARGE_E = "Charge_E"
    VDOT_CHARGE_M = "Charge_M"
    VDOT_CHARGE_T = "Charge_T"
    VDOT_CHARGE_I = "Charge_I"
    VDOT_CHARGE_R = "Charge_R"

    # --- Clés & métadonnées ---
    VDOT_CLE_INTERNE = "Clé interne"
    VDOT_CHECKSUM = "Checksum table"
    VDOT_DERNIERE_MAJ = "Dernière mise à jour"

    # ⚠️ Ne pas redéclarer ENVIRONNEMENT ici
    # ATFIELDS.ENVIRONNEMENT doit être utilisé globalement

    # =================================================
    # 📘 TABLE : RÉFÉRENTIEL NIVEAUX
    # =================================================

    RNIV_NIVEAU = "Niveau"
    RNIV_CLE_NIVEAU = "Clé_niveau"
    RNIV_MODE = "Mode"
    RNIV_DESCRIPTION = "Description niveau"
    RNIV_OBJECTIF_TYPE = "Objectif type"

    RNIV_VDOT_MIN = "VDOT_min"
    RNIV_VDOT_MAX = "VDOT_max"

    RNIV_NB_JOURS_MIN = "Nb_jours_min"
    RNIV_NB_JOURS_MAX = "Nb_jours_max"

    RNIV_NB_SEANCES_MIN = "Nb_séances_min"
    RNIV_NB_SEANCES_MAX = "Nb_séances_max"

    RNIV_DUREE_MIN = "Durée_min"
    RNIV_DUREE_MAX = "Durée_max"

    RNIV_CHARGE_SEANCE_MAX = "Charge_séance_max"
    RNIV_CHARGE_MAX_NIVEAU = "Charge_max_niveau"
    RNIV_CHARGE_CIBLE_HEBDO = "Charge_cible_hebdo"

    RNIV_CLE_COMPLETE = "Clé complète"
    RNIV_CLE_COMPLETE_SIMPLE = "Clé complète simplifiée"

    RNIV_MESSAGE_COH = "Message_cohérence"
    RNIV_MESSAGE_DISPO = "Message_disponibilité"

    RNIV_COHERENCE_AUTO = "Cohérence_auto"
    RNIV_MODE_SIMPLIFIE = "Mode simplifié"

    # ⚠️ Ne pas redéclarer ENVIRONNEMENT ici.
    # Utiliser ATFIELDS.ENVIRONNEMENT si le champ existe dans Airtable.

    # =================================================
    # 🎛 TABLE : RÉFÉRENTIEL CATÉGORIES SÉANCES
    # =================================================

    RCAT_ID_CATEGORIE = "ID Catégorie"
    RCAT_CLE_COURTE = "Clé courte"

    RCAT_PHASES = "Phases"
    RCAT_DESCRIPTION = "Description"

    RCAT_TYPE_ALLURE = "Type d’allure"

    RCAT_DUREE_MIN = "Durée min (min)"
    RCAT_DUREE_MAX = "Durée max (min)"

    RCAT_DISTANCE_MOY = "Distance moyenne estimée (km)"
    RCAT_CHARGE_REF = "Charge de référence"

    # Il y a un doublon dans Airtable → champs identiques :
    # "ID Catégorie"
    # Comme pour Séances Types, on le gère en second champ distinct.
    RCAT_ID_CATEGORIE_2 = "ID Catégorie"

    RCAT_DESCRIPTION_COMPLETE = "Description complète"
    RCAT_NOTES_COACH = "Notes / Conseil du coach"

    RCAT_SEANCES_TYPES_ASSOCIEES = "Séances types associées"
    RCAT_FORMULES = "Formules internes éventuelles"

    RCAT_ETAT = "État / Validité / Flags"

    # ⚠️ Ne pas déclarer Environnement ici.
    # Utiliser ATFIELDS.ENVIRONNEMENT si le champ existe dans Airtable.

    # =================================================
    # 🎛 TABLE : SCÉNARIOS DE VALIDATION
    # =================================================

    SVAL_ID_SCENARIO = "ID_Scénario"
    SVAL_NOM = "Nom"
    SVAL_MODE = "Mode"
    SVAL_GENRE = "Genre"
    SVAL_AGE = "Âge"
    SVAL_VDOT_TEST = "VDOT_test"
    SVAL_OBJECTIF = "Objectif"
    SVAL_DISTANCE_OBJECTIF = "Distance objectif"
    SVAL_DUREE_PREVUE = "Durée_prevue"

    SVAL_JOURS_DISPONIBLES = "Jours_disponibles"
    SVAL_NB_SEANCES_ATTENDUES = "Nb séances attendues"
    SVAL_MESSAGES_ATTENDUS = "Messages attendus"

    SVAL_STATUT = "Statut"
    SVAL_LIEN_COUREUR = "Lien coureur (démo)"

    # =================================================
    # 🛣️ TABLE : Mapping Phase
    # =================================================
    # Running
    MP_DISTANCE = "Distance"
    MP_PHASE_CLE = "Phase (clé)"
    MP_ORDRE_PHASE = "Ordre phase"
    MP_SEM_DEBUT = "Semaine début"
    MP_SEM_FIN = "Semaine fin"
    MP_PCT_DEBUT = "Pct_debut"
    MP_PCT_FIN = "Pct_fin"


    # ⚠️ Comme toujours : ne pas redéclarer ENVIRONNEMENT ici.
# ============================================================
# Séances Types - Champs Airtable (namespace ST)
# ============================================================

class ST:
    NOM = "Modèle"
    CLE_SEANCE = "clé_séance"
    CATEGORIE = "Catégorie"
    TYPE_ALLURE = "Type allure"

    MODE = "Mode"
    PHASE_CIBLE = "Phase cible"
    NIVEAUX = "Niveau"           # liste Airtable

    DUREE = "Durée (min)"
    DISTANCE_MOY = "Distance moyenne"

    VDOT_MIN = "VDOT_min"
    VDOT_MAX = "VDOT_max"

    DESCRIPTION = "Description"
    CONSEIL_COACH = "Conseil coach"

    KIDS = "Kids"
    VITALITE = "Vitalité"
    HYROX = "Hyrox"

# =====================================================
# Utilitaires
# =====================================================

def get_field(record: dict, field: str, default=None):
    """
    Récupère un champ dans un record Airtable en toute sécurité.
    record : dict issu de AirtableService
    field : champ défini dans ATFIELDS
    """
    try:
        return record.get("fields", {}).get(field, default)
    except Exception:
        return default