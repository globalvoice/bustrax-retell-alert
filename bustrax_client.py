import os
import requests

LOGIN_URL = os.getenv("BUSTRAX_LOGIN_URL")
API_URL = os.getenv("BUSTRAX_API_URL")
USERNAME = os.getenv("BUSTRAX_USERNAME")
PASSWORD = os.getenv("BUSTRAX_PASSWORD")
VER = os.getenv("BUSTRAX_VER", "1.0.1")
BUNIT = os.getenv("BUSTRAX_BUNIT")
ANTICIPATION_MINUTES = os.getenv("BUSTRAX_ANTICIPATION_MINUTES", "45")

def get_bustrax_token():
    resp = requests.post(
        LOGIN_URL,
        data={
            "username": USERNAME,
            "password": PASSWORD,
            "version": "2.0"
        }
    )
    resp.raise_for_status()
    data = resp.json()
    # Get token from 3rd position as per doc
    token = data["data"][2]["api_key"]
    return token

def get_route_tracking(token):
    form = {
        "data[iuser]": USERNAME,
        "data[bttkn]": token,
        "data[ver]": VER,
        "data[bunit]": BUNIT,
        "data[anticipation_minutes]": ANTICIPATION_MINUTES,
        "type": "get_route_tracking"
    }
    resp = requests.post(API_URL, data=form)
    resp.raise_for_status()
    return resp.json()
