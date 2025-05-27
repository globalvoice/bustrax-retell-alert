import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from bustrax_client import get_driver_alerts
from retell_client import call_driver
from utils import format_number

app = FastAPI()

API_KEY = os.getenv("BUSTRAX_API_KEY")
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")

@app.post("/check-alerts")
async def check_alerts(request: Request):
    try:
        alerts = get_driver_alerts(API_KEY)
        # Example: look for 3 red alarms in the alerts
        red_alarms = [a for a in alerts if a["color"] == "red"]
        if len(red_alarms) >= 3:
            driver = red_alarms[0]["driver"]  # Get the driver to call
            phone = format_number(driver["cellphone"])
            call_driver(
                api_key=RETELL_API_KEY,
                from_number=RETELL_FROM_NUMBER,
                to_number=phone,
                agent_id=RETELL_AGENT_ID,
                driver_name=driver["name"]
            )
            return {"status": "Outbound call triggered", "driver": driver}
        else:
            return {"status": "No action", "alert_count": len(red_alarms)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
