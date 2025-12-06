# scenarios/dispatcher.py

from core.utils.logger import log_info
from core.internal_result import InternalResult
from scenarios.agregateur.scn_1 import run_scn_1
from scenarios.agregateur.scn_2 import run_scn_2
# (si besoin : SCN_3, SCN_6, etc.)

class SmartCoachContext:
    def __init__(self, scenario, record_id, payload):
        self.scenario = scenario
        self.record_id = record_id
        self.payload = payload or {}

def dispatch_scenario(scn_name: str, record_id: str, payload: dict = None):
    log_info(f"Dispatcher → Scénario demandé : {scn_name}")

    # 1) Construire le contexte complet
    context = SmartCoachContext(
        scenario=scn_name,
        record_id=record_id,
        payload=payload or {}
    )

    # SCN_1 → Normalisation + métadonnées
    if scn_name == "SCN_1":
        return run_scn_1(context)

    # ======================================================
    # SCN_2 = Construction des slots
    # NE PEUT PAS être appelé sans data_scn1
    # ======================================================
    if scn_name == "SCN_2":

        # Récupération éventuelle envoyée par Make / API
        data_scn1 = context.payload.get("data_scn1")

        if not data_scn1:
            # 👉 SCN_1 doit être exécuté automatiquement
            norm_res = run_scn_1(context)

            if norm_res.status != "ok":
                return norm_res

            # On injecte SEULEMENT les données utiles → norm_res.data
            data_scn1 = norm_res.data

        # Maintenant data_scn1 est garanti OK
        return run_scn_2(context, data_scn1)

    # ======================================================
    if scn_name == "SCN_3":
        raise ValueError("SCN_3 non encore implémenté")

    if scn_name == "SCN_6":
        raise ValueError("SCN_6 non encore implémenté")

    # ======================================================
    raise ValueError(f"Scénario inconnu : {scn_name}")

