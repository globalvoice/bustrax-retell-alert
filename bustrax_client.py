import os
import httpx

USERNAME = os.getenv("BUSTRAX_USERNAME")
PASSWORD = os.getenv("BUSTRAX_PASSWORD")

# Provide fallbacks if env vars aren’t set
AUTH_URL  = os.getenv(
    "BUSTRAX_AUTH_URL",
    "https://w2.bustrax.io/wp-admin/ajax-auth.php"
)
TRACK_URL = os.getenv(
    "BUSTRAX_TRACK_URL",
    "https://api.bustrax.io/engine/get_json.php"
)

async def get_bustrax_token() -> str:
    params = {
        "action":  "login",
        "username": USERNAME,
        "password": PASSWORD,
        "version": "2.0",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(AUTH_URL, params=params)

        # ─── DEBUG OUTPUT ───────────────────────────────────────────────
        print("→ Bustrax LOGIN URL:", r.url)
        print("→ Login response text:", repr(r.text))
        # ────────────────────────────────────────────────────────────────

        r.raise_for_status()
        parts = r.text.strip().split(",")
        if len(parts) < 4:
            raise Exception(f"Unexpected auth response: {r.text!r}")
        return parts[3].strip()

async def get_route_tracking(token: str) -> dict:
    data = {
        "data[iuser]":            USERNAME,
        "data[bttkn]":            token,
        "data[ver]":              "1.0.1",
        "data[bunit]":            os.getenv("BUSTRAX_BUSINESS_UNIT", "lip_vdm"),
        "data[anticipation_minutes]": os.getenv("BUSTRAx_ANTICIPATION_MINUTES", "45"),
        "data[after_trip_minutes]":     "15",
        "type": "get_route_tracking",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(TRACK_URL, data=data)
        r.raise_for_status()
        return r.json()
