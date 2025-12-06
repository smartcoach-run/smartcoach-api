# core/context.py

from typing import Any, Dict, Optional
from pydantic import BaseModel

class SmartCoachContext(BaseModel):
    """
    Contexte central SmartCoach, partagé entre tous les scénarios.
    Toutes les étapes (SCN_0a → SCN_6) lisent ou enrichissent ce contexte.
    """
    course_id: Optional[str] = None       # recXXXXXXXX
    course_table_id: Optional[str] = None # tblXXXXXXXX
    
    # ----------------------------------------------------------
    # 🌐 Paramètres Airtable
    # ----------------------------------------------------------
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None

    # ----------------------------------------------------------
    # 🏃 Données coureur : record brut Airtable
    # ----------------------------------------------------------
    course_record: Optional[Dict[str, Any]] = None

    # ----------------------------------------------------------
    # 🔄 Données enrichies au cours des scénarios
    # ----------------------------------------------------------
    normalized: Optional[Dict[str, Any]] = None        # sortie SCN_0a
    optimized_days: Optional[Dict[str, Any]] = None     # sortie SCN_0b

    week_structure: Optional[Dict[str, Any]] = None     # sortie SCN_1 step4
    slots: Optional[Dict[str, Any]] = None              # sortie SCN_0d
    phases: Optional[Any] = None                        # sortie SCN_0e

    # ----------------------------------------------------------
    # 📚 Modèles "Séances Types"
    # ----------------------------------------------------------
    models_seance_types: Optional[list] = None

    # ----------------------------------------------------------
    # 🛠️ Autoriser l'ajout dynamique de champs
    # ----------------------------------------------------------
    class Config:
        extra = "allow"
    


