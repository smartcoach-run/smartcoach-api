from typing import Any, Dict
from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from scenarios.extractors import extract_record_fields

logger = get_logger("SCN_0a")


class SCN_0a:

    @staticmethod
    def run(context: SmartCoachContext) -> InternalResult:
        try:
            logger.info("Début SCN_0a → Validation & normalisation")

            record = context.record_raw

            if not record:
                return InternalResult.make_error(
                    message="Record Airtable vide ou introuvable",
                    context=context,
                    source="SCN_0a"
                )

            # --------------------------
            # Extraction normalisée
            # --------------------------
            try:
                extracted = extract_record_fields(record)
            except Exception as e:
                return InternalResult.make_error(
                    message=f"Erreur extraction champs : {e}",
                    context=context,
                    source="SCN_0a"
                )

            # --------------------------
            # Champs obligatoires via clés normalisées
            # --------------------------
            required_fields = {
                "prenom": "Prénom",
                "email": "Email"
            }

            missing = [
                label for key, label in required_fields.items()
                if not extracted.get(key)
            ]

            if missing:
                return InternalResult.make_error(
                    message=f"Champ manquant : {', '.join(missing)}",
                    context=context,
                    source="SCN_0a"
                )

            # --------------------------
            # Succès
            # --------------------------
            logger.info(
                f"SCN_0a OK → Normalisation réussie pour record {context.record_id}"
            )

            return InternalResult.make_success(
                message="SCN_0a OK",
                data=extracted,
                context=context,
                source="SCN_0a"
            )

        except Exception as e:
            logger.exception("SCN_0a → Exception : %s", e)
            return InternalResult.make_error(
                message=f"Erreur SCN_0a : {e}",
                context=context,
                source="SCN_0a"
            )


def run_scn_0a(context: SmartCoachContext) -> InternalResult:
    return SCN_0a.run(context)
