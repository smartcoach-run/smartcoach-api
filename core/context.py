from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class SmartCoachContext(BaseModel):
    """
    Contexte unique échangé entre le Dispatcher, les SCN fonctionnels
    et les scénarios SOCLE (SCN_0x).

    Aucune logique métier ici.
    Simple conteneur de données.
    """

    # --- Identité technique -------------------------
    scenario: str = Field(default="", description="Nom du scénario demandé")
    record_id: str = Field(default="", description="ID Airtable du record")

    # --- Données brutes Fillout / Airtable ----------
    record_raw: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Record Airtable brut (avant SCN_0a)"
    )

    # --- Données normalisées (remplies par SCN_0a) ---
    record_norm: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Record normalisé (sortie SCN_0a)"
    )

    # --- Résultats intermédiaires SOCLE -------------
    jours_result: Optional[Dict[str, Any]] = None       # sortie SCN_0b
    vdot_result: Optional[Dict[str, Any]] = None        # sortie SCN_0c
    structure_raw: Optional[Dict[str, Any]] = None      # sortie SCN_0d
    structure_phased: Optional[Dict[str, Any]] = None   # sortie SCN_0e
    final_json: Optional[Dict[str, Any]] = None         # sortie SCN_0f

    # --- MÉTHODE ESSENTIELLE POUR LE PIPELINE ------
    def update(self, data: Dict[str, Any]):
        """
        Met à jour dynamiquement le contexte avec les clés/valeurs fournies.
        """
        for key, value in data.items():
            setattr(self, key, value)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
