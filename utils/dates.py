from datetime import date, datetime

def get_day_index_from_date(
    target_date: date | datetime,
    start_date: date | datetime | None = None
) -> int:
    """
    Calcule l'index du jour (0-based) entre start_date et target_date.

    Exemples :
    - start_date = 2025-01-01
    - target_date = 2025-01-01 → 0
    - target_date = 2025-01-02 → 1

    Si start_date n'est pas fourni, on utilise la date du jour.
    """

    if start_date is None:
        start_date = date.today()

    # Normalisation en date (au cas où on reçoit des datetime)
    if isinstance(start_date, datetime):
        start_date = start_date.date()

    if isinstance(target_date, datetime):
        target_date = target_date.date()

    delta = target_date - start_date
    return delta.days
