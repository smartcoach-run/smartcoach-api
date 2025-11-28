# core/utils/logger.py
# Logger SmartCoach - v1.1
# Niveaux, couleurs, format enrichi, compatibilité API.

import datetime
import os
import logging
import sys

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

# =====================================================
# Logger factory compatible avec toute l’architecture
# =====================================================

def get_logger(name: str):
    """
    Retourne un logger configuré avec :
    - format uniforme
    - niveau INFO par défaut
    - sortie standard (console)
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s ┊ %(name)s ┊ %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# =====================================================
# Compatibilité avec ton ancien système
# =====================================================

root_logger = get_logger("ROOT")


def log_info(message: str, module: str = "APP"):
    root_logger.info(f"{module} → {message}")


def log_error(message: str, module: str = "APP"):
    root_logger.error(f"{module} → {message}")