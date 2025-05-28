import os
import time
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from bustrax_client import get_bustrax_token, get_route_tracking
from retell_client import make_retell_call

app = FastAPI()

COUNTRY_CODE   = os.getenv("COUNTRY_CODE", "52")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))


def format_number(phone: str) -> str:
    p = phone.strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        if not p.startswith(COUNTRY_CODE):
            p = COUNTRY_CODE.lstrip("+") + p.lstrip("0")
        p = "+" + p
    return p


def should_trigger_alarm(item: dict) -> bool:
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


async def check_and_alert() -> dict:
    summary = {"checked": 0, "triggered": 0, "errors": []}
    try:
        token    = await get_bustrax_token()
        tracking = await get_route_tracking(token)
        data     = tracking.get("data", [])

        for item in data:
            summary["checked"] += 1
            if should_trigger_alarm(item):
                to_number   = format_number(item["cellphone"])
                driver_name = item.get("driver_name", "")
                try:
                    await make_retell_call(to_number, driver_name)
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
    result = await check_and_alert()
    return JSONResponse(status_code=200, content=result)


if __name__ == "__main__":
    # Script mode: run every CHECK_INTERVAL seconds
    while True:
        print("Running check_and_alert()…")
        summary = asyncio.run(check_and_alert())
        print(
            f"checked={summary['checked']}, "
            f"triggered={summary['triggered']}"
        )
        if summary["errors"]:
            print("errors:", summary["errors"])
        time.sleep(CHECK_INTERVAL)
