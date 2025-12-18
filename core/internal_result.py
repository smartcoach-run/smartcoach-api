# =====================================================================
#  InternalResult - SmartCoach v2025
#  Objet standardisé pour transporter : statut, message, data, context
#  Compatible avec tous les scénarios SCN_0a → SCN_6
# =====================================================================

class InternalResult:
    """
    Format standardisé utilisé dans tous les scénarios SmartCoach.
    """
    def __init__(self, status="ok", message=None, data=None, context=None, source=None):
        self.status = status                # "ok" ou "error"
        self.message = message              # message informatif
        self.data = data or {}              # données utiles
        self.context = context              # SmartCoachContext
        self.source = source                # nom du scénario
        self.success = (status == "ok")     # bool simplifié

    # -----------------------------------------------------------------
    #    ✓ SUCCESS
    # -----------------------------------------------------------------
    @classmethod
    def ok(cls, message=None, data=None, context=None, source=None):
        """
        Standard success result.
        """
        return cls(
            status="ok",
            message=message,
            data=data,
            context=context,
            source=source
        )

    @classmethod
    def make_success(cls, data=None, message=None, context=None, source=None):
        """
        Alias utilisé dans certains anciens modules.
        """
        return cls.ok(
            message=message,
            data=data,
            context=context,
            source=source
        )

    # -----------------------------------------------------------------
    #    ✗ ERROR
    # -----------------------------------------------------------------
    @classmethod
    def error(cls, message=None, data=None, context=None, source=None):
        """
        Standard error result.
        """
        return cls(
            status="error",
            message=message,
            data=data,
            context=context,
            source=source
        )

    @classmethod
    def make_error(cls, message=None, data=None, context=None, source=None):
        """
        Alias utilisé dans certains anciens modules.
        """
        return cls.error(
            message=message,
            data=data,
            context=context,
            source=source
        )

    @classmethod
    def nok(cls, message=None, data=None, context=None, source=None):
        """
        Compatibilité historique SmartCoach.
        Fonctionne comme error().
        """
        return cls.error(
            message=message,
            data=data,
            context=context,
            source=source
        )

    # -----------------------------------------------------------------
    #   Helper
    # -----------------------------------------------------------------
    def __repr__(self):
        return f"InternalResult(status={self.status}, message={self.message}, data={self.data})"
    # -----------------------------------------------------------------
    #   API serialization
    # -----------------------------------------------------------------
    def to_api(self) -> dict:
        """
        Format standard exposé par l'API SmartCoach.
        """
        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "context": self.context,
            "source": self.source,
        }
