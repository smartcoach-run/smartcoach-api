from datetime import datetime

class SmartCoachContext:
    """
    Contexte central du moteur SmartCoach.
    Contient :
      - Identité de la demande (record_id, env, source)
      - Données venant d’Airtable
      - Données normalisées
      - Résultats du scoring (scénario)
      - Messages + erreurs
      - Debug / logs
    """

    def __init__(self, record_id, env="dev", debug=False, source="api"):
        self.record_id = record_id
        self.env = env
        self.debug = debug
        self.source = source
        self.start = datetime.now()

        # Données brutes
        self.fetch_raw = None

        # Données normalisées
        self.normalized = None

        # Résultats scénarios
        self.scenario_id = None
        self.score_scenario = None

        # Communication API → Make
        self.errors = []
        self.messages = []

    def add_error(self, code, message, context=None):
        self.errors.append({
            "code": code,
            "message": message,
            "context": context or {}
        })

    def add_message(self, text):
        self.messages.append(text)

    def to_public_dict(self):
        return {
            "record_id": self.record_id,
            "scenario_id": self.scenario_id,
            "score_scenario": self.score_scenario,
            "messages": self.messages,
            "errors": self.errors,
        }
    
