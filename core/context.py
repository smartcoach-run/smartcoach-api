from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class SmartCoachContext(BaseModel):
    """
    Contexte unique échangé entre le Dispatcher, les SCN fonctionnels
    et les scénarios SOCLE (SCN_0x).

    Aucune logique métier ici.
    Simple conteneur de données.
    """
    user: dict = {}
    objectifs: dict = {}
    semaines: list = []
    jours_optimises: list = []
    phases: list = []

    # --- AJOUTS CRITIQUES POUR SCN_2 / SCN_3 / SCN_6 ---
    slots_by_week: dict = Field(default_factory=dict)
    sessions_targets: list = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
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
    def merge_result(self, result):
        """
        Merge propre d'un InternalResult dans le contexte.
        Ne remplace pas les champs existants sauf si explicitement envoyé.
        Permet d’enchaîner SCN_1 → SCN_2 → SCN_3 → SCN_6.
        """

        if not result or not hasattr(result, "data"):
            return

        data = result.data or {}

        for key, value in data.items():
            if value is not None:
                setattr(self, key, value)
    def get(self, key: str, default=None):
        """
        Permet d'accéder au contexte comme un dict : context.get("x")
        tout en restant compatible Pydantic.
        """
        return getattr(self, key, default)


    class Config:
        arbitrary_types_allowed = True
        extra = "allow"