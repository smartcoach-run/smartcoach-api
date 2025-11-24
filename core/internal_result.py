from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InternalResult:
    """
    Structure standardisée de retour du moteur SmartCoach.
    """
    status: str
    messages: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------------------
    # Méthodes utilitaires
    # --------------------------------------------------------------

    @classmethod
    def ok(cls, messages=None, data=None):
        return cls(
            status="ok",
            messages=messages or ["OK"],
            data=data or {}
        )

    @classmethod
    def error(cls, messages=None, data=None):
        return cls(
            status="error",
            messages=messages or ["Erreur"],
            data=data or {}
        )

    def add_message(self, message: str):
        self.messages.append(message)

    def merge_data(self, new_data: Dict[str, Any]):
        self.data.update(new_data)
