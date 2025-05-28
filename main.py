# main.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
# Import format_number from bustrax_client
from bustrax_client import get_bustrax_token, get_route_tracking, format_number
from retell_client import make_retell_call

app = FastAPI()

# --- START DEBUGGING PRINTS FOR ENVIRONMENT VARIABLES ---
# These lines will print the values of your environment variables at startup.
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_TEST_PHONE_NUMBER = os.getenv("RETELL_TEST_PHONE_NUMBER")

print(f"DEBUG: main.py - RETELL_API_KEY (first 10 chars): {str(RETELL_API_KEY)[:10] if RETELL_API_KEY else 'None'}")
print(f"DEBUG: main.py - RETELL_FROM_NUMBER: {RETELL_FROM_NUMBER}")
print(f"DEBUG: main.py - RETELL_AGENT_ID: {RETELL_AGENT_ID}")
print(f"DEBUG: main.py - RETELL_TEST_PHONE_NUMBER: {RETELL_TEST_PHONE_NUMBER}")
# --- END DEBUGGING PRINTS ---

@app.get("/")
async def root():
    return {"status": "ok", "message": "GlobalVoice API is running."}

class TriggerResponse(BaseModel):
    checked: int
    triggered: int
    errors: list[str]

@app.post("/trigger-alarm", response_model=TriggerResponse)
async def trigger_alarm():
    """
    Endpoint to manually trigger the alarm check process.
    It authenticates, fetches route tracking data, evaluates for alarms,
    and triggers Retell.ai calls for 'red' conditions.
    """
    # Initialize response metrics
    checked = 0
    triggered = 0
    errors: list[str] = []

    try:
        # 1) Authenticate with Bustrax
        token = await get_bustrax_token()
        print(f"Successfully obtained Bustrax token: {token[:10]}...") # Print first 10 chars for debug
    except Exception as e:
        print(f"Auth failed: {e}") # Log the error
        raise HTTPException(status_code=500, detail=f"Auth failed: {e}")

    try:
        # 2) Fetch route-tracking data (returns a list of dicts)
        raw_tracking_data = await get_route_tracking(token)
        print(f"Received tracking data: {raw_tracking_data}") # Log the raw data
    except Exception as e:
        print(f"Tracking failed: {e}") # Log the error
        raise HTTPException(status_code=500, detail=f"Tracking failed: {e}")

    # 3) Iterate and evaluate each alarm in the list
    if not isinstance(raw_tracking_data, list):
        errors.append(f"Unexpected data format from Bustrax API: Expected a list, got {type(raw_tracking_data).__name__}. Raw data: {raw_tracking_data}")
        print(f"CRITICAL ERROR: Unexpected data format from Bustrax API: {raw_tracking_data}")
        # If it's not a list, we can't proceed with iteration, so return early
        return {"checked": checked, "triggered": triggered, "errors": errors}

    # Iterate over each alarm dictionary in the list
    for alarm in raw_tracking_data:
        if not isinstance(alarm, dict):
            errors.append(f"Unexpected item in Bustrax data list: Expected a dictionary, got {type(alarm).__name__}. Item: {alarm}")
            print(f"WARNING: Skipping non-dictionary item in tracking data: {alarm}")
            continue # Skip to the next item if it's not a dictionary

        checked += 1 # Only increment checked if it's a valid dictionary item

        # Safely parse fin_kpi
        try:
            fin_kpi_val = float(alarm.get("fin_kpi", 0))
        except (TypeError, ValueError):
            fin_kpi_val = None
            errors.append(f"Invalid fin_kpi value for driver {alarm.get('driver name', 'Unknown')}: {alarm.get('fin_kpi')}")

        err_txt = alarm.get("error", "") or ""
        status_txt = alarm.get("status", "") or ""

        # Check for "red" conditions
        is_red = (
            (fin_kpi_val is not None and fin_kpi_val < -9)
            or ("ini" in err_txt)
            or ("Verificar" in status_txt)
            # You can add 'or True' here temporarily for testing any alarm,
            # but remember to remove it for production:
            # or True
        )

        if is_red:
            print(f"Alarm triggered for driver: {alarm.get('driver name', 'Unknown')}")
            # 4) Format phone and trigger Retell
            phone = format_number(alarm.get("cellphone", ""))
            driver = alarm.get("driver_name", "Unknown") # Corrected key from driver_name to "driver name"

            # --- FOR TESTING ONLY: OVERRIDE PHONE NUMBER ---
            # This block is correctly placed INSIDE the 'if is_red:' condition
            TEST_PHONE_NUMBER = os.getenv("RETELL_TEST_PHONE_NUMBER", None)
            if TEST_PHONE_NUMBER:
                print(f"DEBUG: Overriding driver phone ({phone}) with test number: {TEST_PHONE_NUMBER}")
                phone = format_number(TEST_PHONE_NUMBER) # Ensure it's formatted
            # --- END TEST OVERRIDE ---

            if not phone:
                errors.append(f"Missing or invalid phone number for driver {driver}.")
                print(f"Skipping Retell call: Missing phone for {driver}")
            else:
                try:
                    retell_response = await make_retell_call(to_number=phone, driver_name=driver)
                    triggered += 1
                    print(f"Retell call initiated for {driver} ({phone}): {retell_response}")
                except Exception as e:
                    errors.append(f"Retell failed for {phone} (driver {driver}): {e}")
                    print(f"Retell call failed for {driver} ({phone}): {e}")
        else:
            print(f"No alarm for driver: {alarm.get('driver name', 'Unknown')}. Status: fin_kpi={fin_kpi_val}, error='{err_txt}', status='{status_txt}'")

    # 5) Return summary
    return {"checked": checked, "triggered": triggered, "errors": errors}
