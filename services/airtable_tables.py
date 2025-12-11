# services/airtable_tables.py
# =====================================================
# Référentiel Airtable COMPATIBLE V1 + V2 (multi-env)
# =====================================================

import os
from core.config import config


class ATABLES:

    # Environnement actif : DEV ou PROD
    ENV = config.env.upper()

    # ======================================================
    # 🌍 TABLES AVEC ID VARIABLES (DEV / PROD)
    # ======================================================

    # 🏃‍♂️ Coureurs
    COU_TABLE_ID = os.getenv(f"AIRTABLE_COU_TABLE_{ENV}")

    # 🏋️ Séances
    SEANCES_TABLE_ID = os.getenv(f"AIRTABLE_SEANCES_TABLE_{ENV}")

    # 📘 Séances Types
    SEANCES_TYPES_ID = os.getenv(f"AIRTABLE_SEANCES_TYPES_{ENV}")

    # 📐 VDOT reference
    VDOT_TABLE_ID = os.getenv(f"AIRTABLE_VDOT_TABLE_{ENV}")

    # ⚖️ Référence Jours
    REF_JOURS_ID = os.getenv(f"AIRTABLE_REF_JOURS_{ENV}")

    # 🛣️ Mapping Phase
    MAPPING_PHASES_ID = os.getenv(f"AIRTABLE_MAPPING_PHASES_{ENV}")

    # 🎛️ Référentiel Catégories Séances
    REF_CATEGORIES_SEANCES_ID = os.getenv(f"AIRTABLE_REF_CATEGORIES_SEANCES_{ENV}")

    # 📘 Référentiel Niveaux
    REF_NIVEAUX_ID = os.getenv(f"AIRTABLE_REF_NIVEAUX_{ENV}")

    # 🧩 Slots
    REF_SLOTS_ID = os.getenv(f"AIRTABLE_SLOTS_TABLE_{ENV}")

    # ⚙️ Paramètres phases
    REF_PARAM_PHASES_ID = os.getenv(f"AIRTABLE_PARAM_PHASES_{ENV}")

    # ======================================================
    # 📌 TABLES À ID FIXE
    # ======================================================
    SUIVI_TABLE_ID = "tblZX0WddUYaIeBC9"
    MSGS_TABLE_ID = "tblRiRRtz3HlYJThZ"


    # ======================================================
    # 🧩 BACKWARD COMPATIBILITÉ V1 (pour SCN_1/2/3 existants)
    # ======================================================

    # Les anciens noms utilisés partout dans ton code :
    COU_TABLE = COU_TABLE_ID
    SLOTS = REF_SLOTS_ID
    SEANCES = SEANCES_TABLE_ID
    SEANCES_TYPES = SEANCES_TYPES_ID
    VDOT = VDOT_TABLE_ID
    REF_JOURS = REF_JOURS_ID
    MAPPING_PHASES = MAPPING_PHASES_ID
    REF_CATEGORIES_SEANCES = REF_CATEGORIES_SEANCES_ID
    REF_NIVEAUX = REF_NIVEAUX_ID
    
REF_SEANCES_TYPES_ID = ATABLES.SEANCES_TYPES_ID
SEANCES_TYPES_ID = ATABLES.SEANCES_TYPES_ID

