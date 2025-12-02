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

    # Pour garder une version json-ready si besoin
    record_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Version nettoyée/serialisable du record"
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
    # --- Données nécessaires pour SCN_6 (génération séances) ---
    week_structure: Optional[Dict[str, Any]] = None
    slots: Optional[Any] = None
    phases: Optional[Any] = None    

    # --- Méthodes utilitaires ------------------------
    def update(self, data: Dict[str, Any]) -> "SmartCoachContext":
        """
        Met à jour dynamiquement le contexte avec les clés/valeurs fournies.
        Utilisée par SCN_1 et les scénarios SOCLE.
        """
        if not data:
            return self

        for key, value in data.items():
            setattr(self, key, value)
        return self

    def safe_update(self, data: Optional[Any]) -> "SmartCoachContext":
        """
        Variante plus robuste : accepte dict, BaseModel ou None.
        - None → ne fait rien
        - BaseModel → converti en dict
        - autre type → erreur explicite
        """
        if data is None:
            return self

        # Si on reçoit un autre modèle Pydantic
        if isinstance(data, BaseModel):
            data = data.model_dump()

        if not isinstance(data, dict):
            raise TypeError(
                f"SmartCoachContext.safe_update attend un dict (ou BaseModel/None), "
                f"reçu {type(data)}"
            )

        return self.update(data)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"