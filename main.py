import os
import requests
import json
import psycopg2 # Make sure you have this installed: add 'psycopg2-binary' to your requirements.txt
from datetime import datetime, timedelta # Import timedelta for potential future use or better timestamp management

# ... (your existing imports and functions like format_number, make_retell_call)

# --- NEW DATABASE FUNCTIONS ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    # Ensure DATABASE_URL is set in Render environment variables
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(db_url)

def create_processed_alarms_table(conn):
    """Creates the processed_alarms table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_alarms (
                alarm_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_alarm_processed(conn, alarm_id):
    """Checks if an alarm with the given ID has already been processed."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM processed_alarms WHERE alarm_id = %s", (alarm_id,))
        return cur.fetchone() is not None

def mark_alarm_processed(conn, alarm_id):
    """Marks an alarm as processed by inserting its ID into the database."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO processed_alarms (alarm_id, processed_at) VALUES (%s, %s)",
                    (alarm_id, datetime.now()))
        conn.commit()
# --- END NEW DATABASE FUNCTIONS ---

@app.route("/trigger-alarm", methods=["POST"])
def trigger_alarm():
    app.logger.info("Received request to trigger alarms.")
    # --- Authenticate with Bustrax API ---
    bustrax_username = os.environ.get("BUSTRAX_USERNAME") # Make sure these are set in Render env
    bustrax_password = os.environ.get("BUSTRAX_PASSWORD") # Make sure these are set in Render env

    if not bustrax_username or not bustrax_password:
        app.logger.error("Bustrax username or password not set in environment variables.")
        return jsonify({"status": "error", "message": "Bustrax credentials missing"}), 500

    auth_url = f"https://w2.bustrax.io/wp-admin/ajax-auth.php?action=login&username={bustrax_username}&password={bustrax_password}&version=2.0" [cite: 1]
    try:
        auth_response = requests.get(auth_url)
        auth_response.raise_for_status() # Raise an exception for bad status codes
        auth_data = auth_response.text.split(',')
        bustrax_token = auth_data[2].strip() # Assuming the token is the third comma-separated part [cite: 1]
        app.logger.info(f"Bustrax authentication successful. Token obtained.")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error authenticating with Bustrax: {e}")
        return jsonify({"status": "error", "message": f"Bustrax authentication failed: {e}"}), 500

    # --- Fetch Route Tracking Data ---
    tracking_endpoint = "https://api.bustrax.io/engine/get_json.php" [cite: 2]
    # NOTE: Ensure data[bunit] is correctly set for your business unit. Example: 'lip_vdm' [cite: 2]
    # You might want to get data[bunit] from an environment variable too, e.g., os.environ.get("BUSTRAX_BUNIT")
    # Using a placeholder for now, replace with your actual business unit code.
    bustrax_bunit = os.environ.get("BUSTRAX_BUNIT", "lip_vdm") # Default or set as env var

    tracking_params = {
        "data[iuser]": bustrax_username,
        "data[bttkn]": bustrax_token,
        "data[ver]": "1.0.1", [cite: 2]
        "data[bunit]": bustrax_bunit,
        "data[anticipation_minutes]": "45", [cite: 2]
        "data[after_trip_minutes]": "15", [cite: 3]
        "type": "get_route_tracking" [cite: 2]
    }

    raw_tracking_data = []
    try:
        tracking_response = requests.post(tracking_endpoint, data=tracking_params)
        tracking_response.raise_for_status()
        raw_tracking_data = tracking_response.json()
        app.logger.info(f"Successfully fetched {len(raw_tracking_data)} tracking entries.")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching tracking data from Bustrax: {e}")
        return jsonify({"status": "error", "message": f"Failed to fetch tracking data: {e}"}), 500
    except json.JSONDecodeError as e:
        app.logger.error(f"Error decoding tracking data JSON: {e}")
        return jsonify({"status": "error", "message": f"Failed to decode tracking data: {e}"}), 500


    # --- Process Alarms and Make Calls ---
    retell_agent_id = os.environ.get("RETELL_AGENT_ID")
    retell_api_key = os.environ.get("RETELL_API_KEY")
    retell_from_number = os.environ.get("RETELL_FROM_NUMBER")
    retell_test_phone_number = os.environ.get("RETELL_TEST_PHONE_NUMBER") # Used for testing

    if not all([retell_agent_id, retell_api_key, retell_from_number]):
        app.logger.error("Missing Retell.ai environment variables.")
        return jsonify({"status": "error", "message": "Retell.ai credentials missing"}), 500

    successful_calls = 0
    total_potential_alarms = 0
    conn = None # Initialize database connection variable

    try:
        conn = get_db_connection()
        create_processed_alarms_table(conn) # Ensure table exists

        for alarm in raw_tracking_data:
            total_potential_alarms += 1
            # Using 'trip' as the unique ID for the alarm instance
            # Consider a composite key if one trip can have multiple *distinct* alarms you want to track separately
            alarm_id = alarm.get("trip")
            if not alarm_id:
                app.logger.warning(f"Skipping alarm due to missing 'trip' ID: {alarm}")
                continue # Skip alarms without a unique ID

            # Check if this specific alarm (by trip ID) has already been processed
            if is_alarm_processed(conn, alarm_id):
                app.logger.info(f"Alarm for trip {alarm_id} already processed. Skipping.")
                continue # Skip if already processed

            fin_kpi = alarm.get("fin_kpi", 0) [cite: 4]
            error_status = alarm.get("error", "") [cite: 4]
            general_status = alarm.get("status", "") [cite: 4]

            alarm_triggered = False

            # Condition 1: fin_kpi is less than -9 [cite: 7]
            if fin_kpi < -9:
                alarm_triggered = True
                app.logger.info(f"Trigger condition met: fin_kpi={fin_kpi} < -9 for trip {alarm_id}")
            # Condition 2: 'ini' found in error status [cite: 7]
            elif "ini" in error_status:
                alarm_triggered = True
                app.logger.info(f"Trigger condition met: 'ini' in error status ('{error_status}') for trip {alarm_id}")
            # Condition 3: 'Verificar' found in general status [cite: 7]
            elif "Verificar" in general_status:
                alarm_triggered = True
                app.logger.info(f"Trigger condition met: 'Verificar' in general status ('{general_status}') for trip {alarm_id}")

            if alarm_triggered:
                # Extracting information for the call
                # Corrected driver name key: "driver_name"
                driver = alarm.get("driver_name", "Unknown")
                car = alarm.get("car", "Unknown")
                route_desc = alarm.get("rdes", "Unknown Route")
                trip_id = alarm.get("trip", "Unknown Trip ID")
                start_time = alarm.get("start_time", "Unknown Start Time")

                # Determine the recipient number
                # Use test number for testing, otherwise the driver's cellphone
                to_number_raw = alarm.get("cellphone") [cite: 4]
                to_number = format_number(to_number_raw) if to_number_raw else retell_test_phone_number

                if to_number == retell_test_phone_number:
                    app.logger.warning(f"Using test phone number ({retell_test_phone_number}) for trip {alarm_id} due to missing/invalid cellphone.")
                else:
                    app.logger.info(f"Using driver's cellphone ({to_number}) for trip {alarm_id}.")


                app.logger.info(f"Attempting Retell.ai call for trip {alarm_id} (Driver: {driver}, Car: {car}, Route: {route_desc})")
                try:
                    make_retell_call(
                        from_number=retell_from_number,
                        to_number=to_number,
                        agent_id=retell_agent_id,
                        # Pass dynamic data to the agent if your Retell.ai agent script supports it
                        driver_name=driver,
                        car_number=car,
                        route_description=route_desc,
                        trip_id=trip_id,
                        start_time=start_time,
                        kpi=str(fin_kpi), # Convert to string if agent expects string
                        error_message=error_status,
                        status_message=general_status
                    )
                    successful_calls += 1
                    mark_alarm_processed(conn, alarm_id) # Mark as processed AFTER successful call attempt
                    app.logger.info(f"Call initiated and alarm {alarm_id} marked as processed.")
                except Exception as call_e:
                    app.logger.error(f"Error making Retell.ai call for trip {alarm_id}: {call_e}")
            else:
                app.logger.info(f"No alarm condition met for trip {alarm_id}. Status: fin_kpi={fin_kpi}, error='{error_status}', status='{general_status}'")

    except Exception as e:
        app.logger.error(f"Error during alarm processing or database operation: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal server error during alarm processing: {e}"}), 500
    finally:
        if conn:
            conn.close() # Ensure database connection is closed

    response_message = f"Alarm check completed. Processed {total_potential_alarms} entries. Initiated {successful_calls} new calls."
    app.logger.info(response_message)
    return jsonify({"status": "success", "message": response_message})
