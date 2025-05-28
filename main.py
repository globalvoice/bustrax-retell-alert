import os
import requests
import json
import psycopg2
from datetime import datetime
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

# Load environment variables for local development (Render handles them automatically)
load_dotenv()

app = FastAPI()

# --- Database Functions (Remain largely the same) ---
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(db_url)

def create_processed_alarms_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_alarms (
                alarm_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_alarm_processed(conn, alarm_id):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM processed_alarms WHERE alarm_id = %s", (alarm_id,))
        return cur.fetchone() is not None

def mark_alarm_processed(conn, alarm_id):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO processed_alarms (alarm_id, processed_at) VALUES (%s, %s)",
                    (alarm_id, datetime.now()))
        conn.commit()

# --- Retell.ai Call Function (Remains the same for now, but needs crucial fix - see below) ---
def format_number(number):
    # Your existing number formatting logic
    if number and len(number) == 10:
        return "+1" + number
    elif number and number.startswith("+"):
        return number
    return None

def make_retell_call(from_number, to_number, agent_id, **agent_parameters):
    # Your existing Retell.ai call logic
    api_key = os.environ.get("RETELL_API_KEY")
    if not api_key:
        raise ValueError("RETELL_API_KEY environment variable is not set.")

    url = "https://api.retellai.com/v2/create-phone-call"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from_number": from_number,
        "to_number": to_number,
        "agent_id": agent_id,
        "metadata": agent_parameters # <--- THIS IS THE PROBLEM LINE - MUST BE CHANGED
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes
        response_data = response.json()
        print(f"Retell.ai call initiated successfully: {response_data}")
        return response_data
    except requests.exceptions.RequestException as e:
        print(f"Error initiating Retell.ai call: {e}")
        if e.response:
            print(f"Response content: {e.response.text}")
        raise # Re-raise the exception after logging


@app.post("/trigger-alarm") # <-- FastAPI route decorator
async def trigger_alarm(): # <-- FastAPI functions are often async
    print("Received request to trigger alarms.") # Use print or proper FastAPI logging
    # --- Authenticate with Bustrax API ---
    bustrax_username = os.environ.get("BUSTRAX_USERNAME")
    bustrax_password = os.environ.get("BUSTRAX_PASSWORD")

    if not bustrax_username or not bustrax_password:
        # Use HTTPException for FastAPI
        raise HTTPException(status_code=500, detail="Bustrax credentials missing")

    auth_url = f"https://w2.bustrax.io/wp-admin/ajax-auth.php?action=login&username={bustrax_username}&password={bustrax_password}&version=2.0"
    try:
        auth_response = requests.get(auth_url)
        auth_response.raise_for_status()
        auth_data = auth_response.text.split(',')
        bustrax_token = auth_data[3].strip() # <--- This was changed from auth_data[2] to auth_data[3]
        print(f"Bustrax authentication successful. Token obtained: {bustrax_token}")
    except requests.exceptions.RequestException as e:
        print(f"Error authenticating with Bustrax: {e}")
        raise HTTPException(status_code=500, detail=f"Bustrax authentication failed: {e}")

    # --- Fetch Route Tracking Data ---
    tracking_endpoint = "https://api.bustrax.io/engine/get_json.php"
    bustrax_bunit = os.environ.get("BUSTRAX_BUNIT", "lip_vdm") # Default or set as env var

    tracking_params = {
        "data[iuser]": bustrax_username,
        "data[bttkn]": bustrax_token,
        "data[ver]": "1.0.1",
        "data[bunit]": bustrax_bunit,
        "data[anticipation_minutes]": "45",
        "data[after_trip_minutes]": "15",
        "type": "get_route_tracking"
    }

    raw_tracking_data = []
    try:
        tracking_response = requests.post(tracking_endpoint, data=tracking_params)
        tracking_response.raise_for_status()
        print(f"Bustrax Tracking API Response Status Code: {tracking_response.status_code}")
        print(f"Bustrax Tracking API Raw Response: {tracking_response.text}")
        raw_tracking_data = tracking_response.json()
        print(f"Successfully fetched {len(raw_tracking_data)} tracking entries.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tracking data from Bustrax: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tracking data: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding tracking data JSON: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to decode tracking data: {e}")


    # --- Process Alarms and Make Calls ---
    retell_agent_id = os.environ.get("RETELL_AGENT_ID")
    retell_from_number = os.environ.get("RETELL_FROM_NUMBER")
    retell_test_phone_number = os.environ.get("RETELL_TEST_PHONE_NUMBER")

    if not all([retell_agent_id, retell_from_number]):
        raise HTTPException(status_code=500, detail="Retell.ai credentials missing")

    successful_calls = 0
    total_potential_alarms = 0
    conn = None

    try:
        conn = get_db_connection()
        create_processed_alarms_table(conn)

        for alarm in raw_tracking_data:
            total_potential_alarms += 1
            alarm_id = alarm.get("trip") # Use 'trip' or a more unique composite key

            if not alarm_id:
                print(f"Skipping alarm due to missing 'trip' ID: {alarm}")
                continue

            if is_alarm_processed(conn, alarm_id):
                print(f"Alarm for trip {alarm_id} already processed. Skipping.")
                continue

            fin_kpi = alarm.get("fin_kpi", 0)
            error_status = alarm.get("error", "")
            general_status = alarm.get("status", "")

            print(f"DEBUG: Processing trip {alarm_id}. KPI: {fin_kpi}, Error: '{error_status}', Status: '{general_status}'")

            alarm_triggered = False
            if fin_kpi < -9:
                alarm_triggered = True
                print(f"Trigger condition met: fin_kpi={fin_kpi} < -9 for trip {alarm_id}")
            elif "ini" in error_status:
                alarm_triggered = True
                print(f"Trigger condition met: 'ini' in error status ('{error_status}') for trip {alarm_id}")
            elif "Verificar" in general_status:
                alarm_triggered = True
                print(f"Trigger condition met: 'Verificar' in general status ('{general_status}') for trip {alarm_id}")

            if alarm_triggered:
                driver_raw = alarm.get("driver_name") # Get the raw value first
                # Robustly assign driver for speech
                if not driver_raw or driver_raw.strip().lower() in ["none", "unknown", ""]:
                    driver = "Conductor" # Default for speech if driver name is missing/unknown
                else:
                    driver = driver_raw
                
                car = alarm.get("car", "Unknown")
                route_desc = alarm.get("rdes", "Unknown Route")
                trip_id = alarm.get("trip", "Unknown Trip ID")
                start_time = alarm.get("start_time", "Unknown Start Time")

                to_number_raw = alarm.get("cellphone")
                to_number = format_number(to_number_raw) if to_number_raw else retell_test_phone_number

                if to_number == retell_test_phone_number:
                    print(f"Using test phone number ({retell_test_phone_number}) for trip {alarm_id} due to missing/invalid cellphone.")
                else:
                    print(f"Using driver's cellphone ({to_number}) for trip {alarm_id}.")

                print(f"Attempting Retell.ai call for trip {alarm_id} (Driver: {driver}, Car: {car}, Route: {route_desc})")
                try:
                    make_retell_call(
                        from_number=retell_from_number,
                        to_number=to_number,
                        agent_id=retell_agent_id,
                        driver_name=driver,
                        car_number=car,
                        route_description=route_desc,
                        trip_id=trip_id,
                        start_time=start_time,
                        kpi=str(fin_kpi),
                        error_message=error_status,
                        status_message=general_status
                    )
                    successful_calls += 1
                    mark_alarm_processed(conn, alarm_id)
                    print(f"Call initiated and alarm {alarm_id} marked as processed.")
                except Exception as call_e:
                    print(f"Error making Retell.ai call for trip {alarm_id}: {call_e}")
            else:
                print(f"No alarm condition met for trip {alarm_id}. Status: fin_kpi={fin_kpi}, error='{error_status}', status='{general_status}'")

    except Exception as e:
        print(f"Error during alarm processing or database operation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during alarm processing: {e}")
    finally:
        if conn:
            conn.close()

    response_message = f"Alarm check completed. Processed {total_potential_alarms} entries. Initiated {successful_calls} new calls."
    print(response_message)
    return {"status": "success", "message": response_message}
