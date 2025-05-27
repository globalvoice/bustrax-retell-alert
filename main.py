import os
import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from bustrax_client import get_bustrax_token, get_route_tracking
from retell_client import make_retell_call

app = FastAPI()

COUNTRY_CODE       = os.getenv("COUNTRY_CODE", "52")
CHECK_INTERVAL     = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))


def format_number(phone: str) -> str:
    """Ensure phone has +<COUNTRY_CODE> prefix."""
    p = phone.strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        # if it doesn’t already start with the country code, prepend it
        if not p.startswith(COUNTRY_CODE):
            p = COUNTRY_CODE.lstrip("+") + p.lstrip("0")
        p = "+" + p
    return p


def should_trigger_alarm(item: dict) -> bool:
    """
    Returns True if any red-alarm condition is met:
      1) fin_kpi < -9
      2) 'ini' in error
      3) 'Verificar' in status
    """
    try:
        if float(item.get("fin_kpi", 0)) < -9:
            return True
    except (ValueError, TypeError):
        pass

    if "ini" in item.get("error", ""):
        return True

    if "Verificar" in item.get("status", ""):
        return True

    return False


def check_and_alert() -> dict:
    """
    Polls Bustrax, checks each record for red-alarm conditions,
    and if any fire a Retell outbound call.
    Returns a summary dict.
    """
    summary = {"checked": 0, "triggered": 0, "errors": []}

    try:
        token    = get_bustrax_token()
        tracking = get_route_tracking(token)
        data     = tracking.get("data", [])

        for item in data:
            summary["checked"] += 1
            if should_trigger_alarm(item):
                # format phone and call Retell
                to_number   = format_number(item["cellphone"])
                driver_name = item.get("driver_name", "")
                try:
                    make_retell_call(to_number, driver_name)
                    summary["triggered"] += 1
                except Exception as e:
                    summary["errors"].append(
                        f"Retell call failed for {to_number}: {e}"
                    )
    except Exception as e:
        summary["errors"].append(f"Polling failed: {e}")

    return summary


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/trigger-alarm")
async def trigger_alarm():
    result = check_and_alert()
    return JSONResponse(status_code=200, content=result)


if __name__ == "__main__":
    # legacy script mode: run every CHECK_INTERVAL seconds
    while True:
        print("⏱️  Running check_and_alert() …")
        summary = check_and_alert()
        print(f"   → checked={summary['checked']}, triggered={summary['triggered']}")
        if summary["errors"]:
            print("   ❗ errors:", summary["errors"])
        time.sleep(CHECK_INTERVAL)
