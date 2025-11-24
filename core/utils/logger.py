import datetime


# --------------------------------------------------------------
# Formatage commun
# --------------------------------------------------------------
def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _format(level: str, message: str) -> str:
    return f"[{_now()}] {level:<8} — {message}"


# --------------------------------------------------------------
# Niveaux de logs
# --------------------------------------------------------------
def log_info(message: str):
    print(_format("INFO", message))


def log_success(message: str):
    print(_format("SUCCESS", message))


def log_warning(message: str):
    print(_format("WARNING", message))


def log_error(message: str):
    print(_format("ERROR", message))
