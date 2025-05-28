import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bustrax_client import get_bustrax_token, get_route_tracking
from retell_client import make_retell_call

app = FastAPI()

COUNTRY_CODE = os.getenv("COUNTRY_CODE", "52")


@app.get("/")
async def root():
    return {"status": "ok"}


def format_number(phone: str) -> str:
    p = phone.strip()
    if not p.startswith("+"):
        if not p.startswith(COUNTRY_CODE):
            p = COUNTRY_CODE + p.lstrip("0")
        p = "+" + p
    return p


class TriggerResponse(BaseModel):
    checked: int
    triggered: int
    errors: list[str]


@app.post("/trigger-alarm", response_model=TriggerResponse)
async def trigger_alarm():
    checked = 0
    triggered = 0
    errors: list[str] = []

    # 1) Auth
    try:
        token = await get_bustrax_token()
    except Exception as e:
        raise HTTPException(500, detail=f"Auth failed: {e}")

    # 2) Tracking
    try:
        tracking = await get_route_tracking(token)
    except Exception as e:
        raise HTTPException(500, detail=f"Tracking failed: {e}")

    # 3) Check each record for “red” and dial
    for alarm in tracking.get("data", []):
        checked += 1
        fin_kpi   = alarm.get("fin_kpi", 0)
        err_txt   = alarm.get("error", "")
        status_txt= alarm.get("status", "")

        is_red = (
            (isinstance(fin_kpi, (int, float)) and fin_kpi < -9)
            or ("ini" in err_txt)
            or ("Verificar" in status_txt)
        )
        if is_red:
            phone  = format_number(alarm.get("cellphone", ""))
            driver = alarm.get("driver_name", "Unknown")
            try:
                await make_retell_call(to_number=phone, metadata={"driver_name": driver})
                triggered += 1
            except Exception as e:
                errors.append(f"Retell failed for {phone}: {e}")

    return {"checked": checked, "triggered": triggered, "errors": errors}
