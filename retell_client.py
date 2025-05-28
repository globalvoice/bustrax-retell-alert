# retell_client.py
import os
import httpx

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID") # New env var to fetch agent ID

async def make_retell_call(to_number: str, driver_name: str) -> dict:
    """
    Makes an asynchronous call to the Retell.ai API to initiate a phone call.
    """
    url = "https://api.retellai.com/v2/create-phone-call"
    headers = {"Authorization": f"Bearer {RETELL_API_KEY}"}
    payload = {
        "from_number": RETELL_FROM_NUMBER,
        "to_number": to_number,
        "call_type": "phone_call",
        "agent_id": RETELL_AGENT_ID, # ADDED THIS LINE!
        "retell_llm_dynamic_variables": {
            "driver_name": driver_name
        }
    }

    # Add a print statement for debugging the payload - keep this for now
    print(f"DEBUG: Retell Payload: {payload}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
