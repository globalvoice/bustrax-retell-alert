# Bustrax Retell Alert System

- Calls Bustrax API for driver alerts.
- If 3+ red alerts, calls driver using Retell AI.
- Edit `.env` with your API keys.

## Endpoints

- POST `/check-alerts` — checks alerts and triggers call if needed.
