import time
import os
from bustrax_client import get_bustrax_token, get_route_tracking
from retell_client import make_retell_call

COUNTRY_CODE = os.getenv("COUNTRY_CODE", "52")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))

def format_number(phone):
    # Ensures phone has country code
    phone = phone.strip()
    if not phone.startswith("+"):
        if not phone.startswith(COUNTRY_CODE):
            phone = COUNTRY_CODE + phone
        phone = "+" + phone
    return phone

def check_and_alert():
    token = get_bustrax_token()
    tracking = get_route_tracking(token)
    # Example, adjust keys as per actual response
    for alarm in tracking.get("data", []):
        # Example: check for alarm condition; adjust to your schema
        if alarm.get("status") in ["ALERTA_ROJA_1", "ALERTA_ROJA_2", "ALERTA_ROJA_3"]:
            phone = format_number(alarm["cellphone"])
            make_retell_call(phone, alarm["driver_name"])

if __name__ == "__main__":
    while True:
        try:
            check_and_alert()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)
