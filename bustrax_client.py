# bustrax_client.py
import os
import httpx

USERNAME = os.getenv("BUSTRAX_USERNAME")
PASSWORD = os.getenv("BUSTRAX_PASSWORD")
AUTH_URL = os.getenv("BUSTRAX_AUTH_URL")      # e.g. https://w2.bustrax.io/wp-admin/ajax-auth.php
TRACK_URL = os.getenv("BUSTRAX_TRACK_URL")    # e.g. https://api.bustrax.io/engine/get_json.php

async def get_bustrax_token() -> str:
    """
    Call the Bustrax login endpoint, split the CSV-style response,
    and return the long token (4th element).
    """
    params = {
        "action": "login",
        "username": USERNAME,
        "password": PASSWORD,
        "version": "2.0",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(AUTH_URL, params=params)
        r.raise_for_status()
        parts = r.text.strip().split(",")
        if len(parts) < 4:
            raise Exception(f"Unexpected auth response: {r.text!r}")
        # parts[0]=success, [1]=traxion, [2]=TRAXION, [3]=LONG_TOKEN, [4]=c3418...
        token = parts[3].strip()
        return token

async def get_route_tracking(token: str) -> dict:
    """
    Call the Bustrax route-tracking API (form-encoded).
    Returns the parsed JSON payload.
    """
    data = {
        "data[iuser]": USERNAME,
        "data[bttkn]": token,
        "data[ver]": "1.0.1",
        "data[bunit]": os.getenv("BUSTRAX_BUSINESS_UNIT", "lip_vdm"),
        "data[anticipation_minutes]": "45",
        "data[after_trip_minutes]": "15",
        "type": "get_route_tracking",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(TRACK_URL, data=data)
        r.raise_for_status()
        return r.json()
