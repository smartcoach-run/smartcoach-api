from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SmartCoachContext:
    """
    Contexte d'exécution utilisé par tous les scénarios.
    """
    record_id: str
    debug: bool = False
    env: str = "dev"
    source: str = "cli"   # cli, api, make, test…
    metadata: Dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------------------
    # Utilitaires
    # --------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Représentation simple pour logs ou réponses JSON.
        """
        return {
            "record_id": self.record_id,
            "debug": self.debug,
            "env": self.env,
            "source": self.source,
            "metadata": self.metadata,
        }

    def add_meta(self, key: str, value: Any):
        """
        Ajouter une donnée interne au contexte.
        """
        self.metadata[key] = value

    def log_header(self) -> str:
        """
        Entête standardisée pour le logging.
        """
        return f"[CTX] record={self.record_id} source={self.source} env={self.env} debug={self.debug}"
