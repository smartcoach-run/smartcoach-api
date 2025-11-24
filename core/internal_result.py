# core/internal_result.py

class InternalResult:
    """
    Format standard interne utilisé par les scénarios SmartCoach.
    """

    def __init__(self,
                 status: str = "ok",
                 messages=None,
                 data=None,
                 debug: bool = False,
                 source: str = "engine"):
        self.status = status
        self.messages = messages or []
        self.data = data or {}
        self.debug = debug
        self.source = source

    def to_dict(self):
        return {
            "status": self.status,
            "messages": self.messages,
            "data": self.data,
            "debug": self.debug,
            "source": self.source,
        }
