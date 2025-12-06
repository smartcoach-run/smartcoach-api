# models/session_type.py
from pydantic import BaseModel
from typing import Optional, List

class SessionType(BaseModel):
    # Champs actuels SCN_3
    id: Optional[str] = None
    cle_seance: Optional[str] = None
    nom: Optional[str] = None
    categorie: Optional[str] = None
    type_allure: Optional[str] = None
    mode: Optional[str] = None
    phase_cible: Optional[str] = None
    niveaux: List[str] = []
    duree: Optional[float] = None
    distance: Optional[float] = None
    vdot_min: Optional[float] = None
    vdot_max: Optional[float] = None
    description: Optional[str] = None
    conseil_coach: Optional[str] = None

    # Flags
    is_kids: bool = False
    is_vitalite: bool = False
    is_hyrox: bool = False

    # Champs requis par SCN_3 (listes multi)
    univers: List[str] = []
    phase_ids: List[str] = []

    # Champs requis pour SCN_6
    slot_types: List[str] = []
    objectifs: List[str] = []

    # Support interne
    raw_record: Optional[dict] = None
