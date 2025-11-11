from pyairtable import Table
import os
from dotenv import load_dotenv
load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

def airtable_get_all(table_name, **kwargs):
    # Support de formula=... et autres kwargs pyairtable
    table = Table(AIRTABLE_API_KEY, BASE_ID, table_name)
    return table.all(**kwargs)

def airtable_get_one(table_name, id_or_field, value=None):
    table = Table(AIRTABLE_API_KEY, BASE_ID, table_name)
    if value is None:
        # Comportement historique: lookup par record_id
        return table.get(id_or_field)
    # Nouveau: lookup par champ
    formula = f"{{{id_or_field}}} = '{value}'"
    rows = table.all(formula=formula, max_records=1)
    return rows[0] if rows else None
