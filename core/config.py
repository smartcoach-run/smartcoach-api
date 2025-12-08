import os
from pathlib import Path
from dotenv import load_dotenv

# Charge .env à la racine
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


class Config:
    """Configuration centrale SmartCoach."""

    def __init__(self):
        # Environnement actif : dev / prod
        self.env = os.getenv("ENV_MODE", "dev").lower()

        # Clef API Airtable
        self.api_key = os.getenv("AIRTABLE_API_KEY")

        # Base Airtable dépendante de l'environnement
        self.base_id = os.getenv(f"AIRTABLE_BASE_ID_{self.env.upper()}")

        # Si la base ID n'est pas trouvée → fallback pour compatibilité
        if not self.base_id:
            self.base_id = os.getenv("AIRTABLE_BASE_ID")

        # Debug mode
        self.debug = os.getenv("DEBUG_MODE", "0") in ("1", "true", "True")

    def is_valid(self):
        return bool(self.api_key and self.base_id)


config = Config()
