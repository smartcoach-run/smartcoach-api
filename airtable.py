from pyairtable import Table
import os
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

def airtable_get_all(table_name):
    table = Table(AIRTABLE_API_KEY, BASE_ID, table_name)
    return table.all()

def airtable_get_one(table_name, record_id):
    table = Table(AIRTABLE_API_KEY, BASE_ID, table_name)
    return table.get(record_id)
