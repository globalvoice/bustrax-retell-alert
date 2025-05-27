import requests

def call_driver(api_key, from_number, to_number, agent_id, driver_name):
    url = "https://api.retellai.com/v2/create-phone-call"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "from_number": from_number,
        "to_number": to_number,
        "call_type": "phone_call",
        "override_agent_id": agent_id,
        "retell_llm_dynamic_variables": {"driver_name": driver_name}
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()
