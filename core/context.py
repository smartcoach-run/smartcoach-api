# core/context.py

from typing import Any, Dict, Optional
from pydantic import BaseModel

class SmartCoachContext(BaseModel):
    """
    Contexte central SmartCoach, partagé entre tous les scénarios.
    """

    # --- Identifiants d'exécution ---
    slot_id: Optional[str] = None        # recXXXXXX__Jour
    record_id: Optional[str] = None      # recXXXXXX (Coureur)   

    # --- Paramètres généraux ---
    course_id: Optional[str] = None
    course_table_id: Optional[str] = None
    slot_date: Optional[str] = None 
    objective_type: Optional[str] = None
    objective_time: Optional[str] = None
    objectif_normalisé: Optional[str] = None 
    age: Optional[str] = None 
    mode: Optional[str] = None 
    submode: Optional[str] = None
    level: Optional[str] = None
    adaptation: Optional[Dict[str, Any]] = None
    war_room: Optional[Dict[str, Any]] = None 

    # --- Airtable ---
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None

    # --- Données coureur ---
    course_record: Optional[Dict[str, Any]] = None

    # --- Données enrichies par les scénarios ---
    normalized: Optional[Dict[str, Any]] = None
    optimized_days: Optional[Dict[str, Any]] = None
    week_structure: Optional[Dict[str, Any]] = None
    slots: Optional[Dict[str, Any]] = None
    phases: Optional[Any] = None

    # --- Pour cohérence SCN_6 ---
    payload: Optional[Dict[str, Any]] = None
