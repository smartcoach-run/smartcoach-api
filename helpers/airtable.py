import requests

def airtable_get_one(base_id, table_name, record_id, api_key):
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def airtable_get_all(base_id, table_name, api_key, view=None):
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {}
    if view:
        params["view"] = view

    results = []
    offset = None

    while True:
        if offset:
            params["offset"] = offset
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return results