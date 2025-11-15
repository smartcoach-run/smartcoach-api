# smartcoach_core/config.py

import os
from dotenv import load_dotenv

# Charge le fichier .env en local (sur Render, ce sont les variables d'env qui prennent le relai)
load_dotenv()

# ---------------------------------------------------------
# Environnement : dev / test / prod
# ---------------------------------------------------------

SMARTCOACH_ENV = os.getenv("SMARTCOACH_ENV", "dev").lower()

def is_dev() -> bool:
    return SMARTCOACH_ENV == "dev"

def is_test() -> bool:
    return SMARTCOACH_ENV == "test"

def is_prod() -> bool:
    return SMARTCOACH_ENV == "prod"


# ---------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------

def _get_env(name: str, default=None, required: bool = False):
    """
    Récupère une variable d'environnement.
    Si required=True et que la variable est absente → lève une erreur explicite.
    """
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"[CONFIG] Variable d'environnement manquante : {name}")
    return value


# ---------------------------------------------------------
# Airtable : clés & base selon l'environnement
# ---------------------------------------------------------
# On sépare DEV / TEST / PROD.
# - En local : tu remplis AIRTABLE_API_KEY_DEV / AIRTABLE_BASE_ID_DEV dans .env
# - Sur Render PROD : tu définis AIRTABLE_API_KEY_PROD / AIRTABLE_BASE_ID_PROD
# ---------------------------------------------------------

def get_airtable_credentials():
    if is_prod():
        api_key = _get_env("AIRTABLE_API_KEY_PROD", required=True)
        base_id = _get_env("AIRTABLE_BASE_ID_PROD", required=True)
    elif is_test():
        api_key = _get_env("AIRTABLE_API_KEY_TEST", _get_env("AIRTABLE_API_KEY_DEV"), required=True)
        base_id = _get_env("AIRTABLE_BASE_ID_TEST", _get_env("AIRTABLE_BASE_ID_DEV"), required=True)
    else:  # dev par défaut
        api_key = _get_env("AIRTABLE_API_KEY_DEV", required=True)
        base_id = _get_env("AIRTABLE_BASE_ID_DEV", required=True)

    return api_key, base_id


AIRTABLE_API_KEY, AIRTABLE_BASE_ID = get_airtable_credentials()

# ---------------------------------------------------------
# Noms de tables Airtable (identiques entre DEV / PROD)
# → Si un jour tu les renomme, tu pourras surcharger via .env
# ---------------------------------------------------------

TAB_NAME_COUR = os.getenv("AIRTABLE_TABLE_COUR", "👟 Coureurs")
TAB_NAME_SEANCES = os.getenv("AIRTABLE_TABLE_SEANCES", "🏋️ Séances")
TAB_NAME_REF_JOURS = os.getenv("AIRTABLE_TABLE_REF_JOURS", "⚖️ Référence Jours")
TAB_NAME_SUIVI = os.getenv("AIRTABLE_TABLE_SUIVI", "📋 Suivi génération")
TAB_NAME_SCENARIOS = os.getenv("AIRTABLE_TABLE_SCENARIOS", "🎛 Scénarios de validation")
TAB_NAME_COFFRE_FORT = os.getenv("AIRTABLE_TABLE_COFFRE_FORT", "🧰 COFFRE FORT SmartCoach")

# ---------------------------------------------------------
# Divers (API mails, URL publique, debug, etc.)
# ---------------------------------------------------------

SMARTCOACH_DEBUG = os.getenv("SMARTCOACH_DEBUG", "true").lower() == "true"

PUBLIC_BASE_URL = os.getenv(
    "SMARTCOACH_PUBLIC_URL",
    "http://127.0.0.1:8000" if is_dev() else "https://smartcoach.onrender.com"
)

MAIL_API_KEY = os.getenv("MAIL_API_KEY")  # optionnel pour plus tard