import requests

def get_driver_alerts(api_key):
    # This function should call the first/second API and return parsed alerts
    # Replace this with actual API request logic per your API doc
    url = "https://api.bustrax.com/alerts"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["alerts"]
