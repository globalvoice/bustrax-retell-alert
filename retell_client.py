import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER")

def make_retell_call(to_number, driver_name):
    url = "https://api.retellai.com/v2/create-phone-call"
    headers = {"Authorization": f"Bearer {RETELL_API_KEY}"}
    payload = {
        "from_number": RETELL_FROM_NUMBER,
        "to_number": to_number,
        "call_type": "phone_call",
        "retell_llm_dynamic_variables": {
            "driver_name": driver_name
        }
    }
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()
