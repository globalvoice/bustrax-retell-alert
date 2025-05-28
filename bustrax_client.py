# bustrax_client.py
import os
import httpx

USERNAME = os.getenv("BUSTRAX_USERNAME")
PASSWORD = os.getenv("BUSTRAX_PASSWORD")

# Provide fallbacks if env vars aren’t set
# Corrected: Removed ?action=login from default URL, as it's added in params
AUTH_URL = os.getenv(
    "BUSTRAX_AUTH_URL",
    "https://w2.bustrax.io/wp-admin/ajax-auth.php"
)
# Corrected: Changed env var name to BUSTRAX_TRACK_URL to match code
TRACK_URL = os.getenv(
    "BUSTRAX_TRACK_URL",
    "https://api.bustrax.io/engine/get_json.php"
)

COUNTRY_CODE = os.getenv("COUNTRY_CODE", "52") # Moved from main.py, as it's used here for formatting

def format_number(phone: str) -> str:
    """
    Normalize a phone number to E.164 with country code.
    Strips spaces/dashes, removes leading zeros, prepends country code if missing.
    """
    p = str(phone).strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        # remove leading zeros
        p = p.lstrip("0")
        # prepend country code
        if not p.startswith(COUNTRY_CODE):
            p = COUNTRY_CODE + p
        p = "+" + p
    return p

async def get_bustrax_token() -> str:
    """
    Authenticates with the Bustrax API and retrieves an authentication token.
    """
    params = {
        "action": "login",
        "username": USERNAME,
        "password": PASSWORD,
        "version": "2.0", # This is hardcoded to "2.0" in the code, but env var is "1.0.1"
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(AUTH_URL, params=params)

        # ─── DEBUG OUTPUT ───────────────────────────────────────────────
        print("→ Bustrax LOGIN URL:", r.url)
        print("→ Login response status:", r.status_code)
        print("→ Login response text:", repr(r.text))
        # ────────────────────────────────────────────────────────────────

        r.raise_for_status()
        parts = r.text.strip().split(",")
        # The documentation says "tercera posición" (third position), which is index 2.
        # However, the example shows the token as the *fourth* comma-separated part (index 3).
        # We'll stick with index 3 as per the example, but this is a common point of confusion.
        if len(parts) < 4:
            raise Exception(f"Unexpected auth response: {r.text!r} - Expected at least 4 parts.")
        return parts[3].strip()

async def get_route_tracking(token: str) -> dict:
    """
    Fetches route tracking data from the Bustrax API using the provided token.
    """
    data = {
        "data[iuser]": USERNAME,
        "data[bttkn]": token,
        # Corrected: Use env var for version if desired, otherwise keep hardcoded
        "data[ver]": os.getenv("BUSTRAX_VER", "1.0.1"), # Using env var now
        # Corrected: Changed env var name to BUSTRAX_BUSINESS_UNIT to match code
        "data[bunit]": os.getenv("BUSTRAX_BUSINESS_UNIT", "lip_vdm"),
        # Corrected: Fixed typo in env var name (BUSTRAx -> BUSTRAX)
        "data[anticipation_minutes]": os.getenv("BUSTRAX_ANTICIPATION_MINUTES", "45"),
        "data[after_trip_minutes]": "15",
        "type": "get_route_tracking",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(TRACK_URL, data=data)
        r.raise_for_status()
        return r.json()
