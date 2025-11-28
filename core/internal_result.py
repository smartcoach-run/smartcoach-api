# ======================================================================
# InternalResult : objet standard pour retourner les résultats internes
# ======================================================================
print(">>> InternalResult chargé depuis :", __file__)

class InternalResult:
    def __init__(self, status, message=None, data=None, context=None, source=None):
        self.status = status
        self.message = message
        self.data = data or {}
        self.context = context
        self.source = source

    @property
    def success(self):
        return self.status == "ok"

    @classmethod
    def make_success(cls, message=None, data=None, context=None, source=None):
        return cls("ok", message=message, data=data, context=context, source=source)

    @classmethod
    def make_error(cls, message=None, data=None, context=None, source=None):
        return cls("error", message=message, data=data, context=context, source=source)

    @classmethod
    def ok(cls, data=None, message=None, context=None, source=None):
        return cls("ok", message=message, data=data, context=context, source=source)

print(">>> InternalResult a status ?", hasattr(InternalResult("ok"), "status"))
