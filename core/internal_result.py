# core/internal_result.py

class InternalResult:
    """
    Format standard interne utilisé par les scénarios SmartCoach.
    """

    def __init__(
        self,
        status: str = "ok",
        messages=None,
        data=None,
        debug: bool = False,
        source: str = "engine",
    ):
        self.status = status
        self.messages = messages or []
        self.data = data or {}
        self.debug = debug
        self.source = source

    def to_dict(self):
        """
        Conversion en dict pour la réponse API / logs.
        """
        return {
            "status": self.status,
            "messages": self.messages,
            "data": self.data,
            "debug": self.debug,
            "source": self.source,
        }

    # ------------------------------------------------------------------
    # Fabriques pratiques
    # ------------------------------------------------------------------
    @classmethod
    def ok(
        cls,
        data=None,
        messages=None,
        debug: bool = False,
        source: str = "engine",
    ):
        """
        Fabrique d'un résultat OK.
        """
        return cls(
            status="ok",
            data=data,
            messages=messages or [],
            debug=debug,
            source=source,
        )

    @classmethod
    def error(
        cls,
        message,
        data=None,
        debug: bool = False,
        source: str = "engine",
    ):
        """
        Fabrique d'un résultat en erreur.
        """
        if isinstance(message, list):
            messages = message
        else:
            messages = [str(message)]

        return cls(
            status="error",
            data=data or {},
            messages=messages,
            debug=debug,
            source=source,
        )
