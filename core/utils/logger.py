# core/utils/logger.py
# Logger SmartCoach - v1.1
# Niveaux, couleurs, format enrichi, compatibilité API.

import datetime
import os

# -----------------------------------------------------------------------------
# COULEURS
# -----------------------------------------------------------------------------
RESET = "\033[0m"
COLORS = {
    "DEBUG": "\033[90m",   # Gris
    "INFO":  "\033[94m",   # Bleu
    "SUCCESS": "\033[92m", # Vert
    "WARNING": "\033[93m", # Jaune
    "ERROR": "\033[91m",   # Rouge
}

# Désactivation automatique des couleurs via API
DISABLE_COLORS = os.getenv("SMARTCOACH_NO_COLOR", "0") == "1"


def colorize(text: str, level: str) -> str:
    if DISABLE_COLORS:
        return text
    return f"{COLORS.get(level, '')}{text}{RESET}"


# -----------------------------------------------------------------------------
# FORMATTER
# -----------------------------------------------------------------------------
def _format(level: str, message: str, module: str = None) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    module_part = f"{module} ┊ " if module else ""
    base = f"[{timestamp}] {level:<7} ┊ {module_part}{message}"

    return colorize(base, level)


# -----------------------------------------------------------------------------
# PUBLIC
# -----------------------------------------------------------------------------
def log_debug(msg: str, module: str = None):
    print(_format("DEBUG", msg, module))


def log_info(msg: str, module: str = None):
    print(_format("INFO", msg, module))


def log_success(msg: str, module: str = None):
    print(_format("SUCCESS", msg, module))


def log_warning(msg: str, module: str = None):
    print(_format("WARNING", msg, module))


def log_error(msg: str, module: str = None):
    print(_format("ERROR", msg, module))