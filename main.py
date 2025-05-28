import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bustrax_client import get_bustrax_token, get_route_tracking
from retell_client import make_retell_call

app = FastAPI()

COUNTRY_CODE = os.getenv("COUNTRY_CODE", "52")


@app.get("/")
async def root():
    return {"status": "ok"}


def format_number(phone: str) -> str:
    """
    Normalize a Mexican phone number to E.164 with +52.
    Strips spaces/dashes, removes leading zeros, prepends +52 if missing.
    """
    p = phone.strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        # remove leading zeros
        p = p.lstrip("0")
        # prepend country code
        if not p.startswith(COUNTRY_CODE):
            p = COUNTRY_CODE + p
        p = "+" + p
    return p


class TriggerResponse(BaseModel):
    checked: int
    triggered: int
    errors: list[str]


@app.post("/trigger-alarm", response_model=TriggerResponse)
async def trigger_alarm():
    try:
        # 1) Authenticate with Bustrax
        token = await get_bustrax_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth failed: {e}")

    try:
        # 2) Fetch route-tracking data (returns a list)
        raw = await get_route_tracking(token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracking failed: {e}")

    # 3) Normalize to a list of alarms
    alarms = raw if isinstance(raw, list) else raw.get("data", [])
    checked = 0
    triggered = 0
    errors: list[str] = []

    # 4) Evaluate each alarm for "red" conditions
    for alarm in alarms:
        checked += 1

        # Safely parse fin_kpi
        try:
            fin_kpi_val = float(alarm.get("fin_kpi", 0))
        except (TypeError, ValueError):
            fin_kpi_val = None

        err_txt    = alarm.get("error", "") or ""
        status_txt = alarm.get("status", "") or ""

        is_red = (
            (fin_kpi_val is not None and fin_kpi_val < -9)
            or ("ini" in err_txt)
            or ("Verificar" in status_txt)
        )

        if not is_red:
            continue

        # 5) Format phone and trigger Retell
        phone  = format_number(alarm.get("cellphone", ""))
        driver = alarm.get("driver_name", "Unknown")

        try:
            await make_retell_call(to_number=phone, driver_name=driver)
            triggered += 1
        except Exception as e:
            errors.append(f"Retell failed for {phone}: {e}")

    # 6) Return summary
    return {"checked": checked, "triggered": triggered, "errors": errors}
