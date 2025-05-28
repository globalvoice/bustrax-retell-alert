# retell_client.py
import os
import httpx # Changed from 'requests'

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER")

async def make_retell_call(to_number: str, driver_name: str) -> dict:
    """
    Makes an asynchronous call to the Retell.ai API to initiate a phone call.

    Args:
        to_number (str): The recipient's phone number in E.164 format (e.g., "+1234567890").
        driver_name (str): The name of the driver to pass as a dynamic variable to the LLM agent.

    Returns:
        dict: The JSON response from the Retell.ai API.

    Raises:
        httpx.HTTPStatusError: If the API call returns a non-2xx status code.
        httpx.RequestError: For other network-related errors.
    """
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

    async with httpx.AsyncClient() as client: # Use httpx.AsyncClient
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status() # Raise an exception for bad status codes
        return resp.json()
