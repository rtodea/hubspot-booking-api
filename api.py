import os
from datetime import datetime
from typing import Optional, Dict, List, Any

import pytz  # Required: pip install pytz
import requests
from fastapi import FastAPI, Query, HTTPException


# --- Environment Variable ---
# Expected to be set in the environment: HUBSPOT_API_KEY
# Example: export HUBSPOT_API_KEY="your_actual_hubspot_HUBSPOT_API_KEY"

# --- Helper Functions (from the previous script) ---

def convert_duration_ms_to_label(duration_ms_str: str) -> str:
    try:
        milliseconds = int(duration_ms_str)
        if milliseconds < 0:
            raise ValueError("Duration in milliseconds cannot be negative.")
        minutes = milliseconds // (1000 * 60)
        return f"{minutes}min"
    except ValueError:
        return "UnknownDuration"
    except TypeError:
        return "InvalidDurationFormat"


def is_within_business_hours(
        dt_obj: datetime,
        start_hour: int = 9,
        end_hour: int = 17,
        work_days: Optional[List[int]] = None
) -> bool:
    if work_days is None:
        work_days = [0, 1, 2, 3, 4]  # Monday to Friday (Monday=0, Sunday=6)
    if dt_obj.weekday() not in work_days:
        return False
    return start_hour <= dt_obj.hour < end_hour


def process_hubspot_availability(
        hubspot_response_json: Dict[str, Any],
        target_timezone: str,
        apply_business_hours_filter: bool = False,
        business_start_hour: int = 9,
        business_end_hour: int = 17,
        business_work_days: Optional[List[int]] = None
) -> Dict[str, List[str]]:
    transformed_availability: Dict[str, List[str]] = {}
    link_availability_data = hubspot_response_json.get("linkAvailability", {})
    availability_by_duration = link_availability_data.get("linkAvailabilityByDuration", {})

    if not isinstance(availability_by_duration, dict):
        print("Warning: 'linkAvailabilityByDuration' is not a dictionary or is missing.")
        return {}

    try:
        target_tz_obj = pytz.timezone(target_timezone)  # Validate and cache timezone object once
    except pytz.exceptions.UnknownTimeZoneError:
        # This error should be caught before calling this function if validating early
        raise ValueError(f"Unknown or invalid timezone: {target_timezone}")

    for duration_ms_str, details in availability_by_duration.items():
        duration_label = convert_duration_ms_to_label(duration_ms_str)
        available_slots_formatted: List[str] = []

        if not isinstance(details, dict):
            continue

        for slot in details.get("availabilities", []):
            if not isinstance(slot, dict):
                continue
            start_millis = slot.get("startMillisUtc")
            if start_millis is None or not isinstance(start_millis, (int, float)):
                continue

            try:
                utc_dt = datetime.fromtimestamp(start_millis / 1000.0, tz=pytz.utc)
                local_dt = utc_dt.astimezone(target_tz_obj)

                if apply_business_hours_filter:
                    if not is_within_business_hours(
                            local_dt,
                            start_hour=business_start_hour,
                            end_hour=business_end_hour,
                            work_days=business_work_days
                    ):
                        continue

                formatted_slot_time = local_dt.strftime("%A %Y-%m-%d %H:%M")
                available_slots_formatted.append(formatted_slot_time)
            except (ValueError, TypeError) as e:
                print(f"Skipping a slot for duration {duration_label} due to data processing error: {e}")
                continue

        if available_slots_formatted:
            transformed_availability[duration_label] = available_slots_formatted

    return transformed_availability


def fetch_hubspot_meeting_availability(
        hubspot_api_key: str,
        slug: str, timezone: str) -> Dict[str, Any]:
    if not hubspot_api_key:
        raise ValueError("HUBSPOT_API_KEY is not provided internally.")

    url = (f"https://api.hubapi.com"
           f"/scheduler/v3/meetings/meeting-links/book/availability-page"
           f"/{slug}?timezone={timezone}")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {hubspot_api_key}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
        return response.json()
    except requests.exceptions.HTTPError as errh:
        # Logged by the caller if needed, re-raise to be handled by endpoint
        raise
    except requests.exceptions.ConnectionError as errc:
        raise ConnectionError(f"Network connection error to HubSpot: {errc}") from errc
    except requests.exceptions.Timeout as errt:
        raise TimeoutError(f"Request to HubSpot timed out: {errt}") from errt
    except requests.exceptions.JSONDecodeError as jerr:
        # Log the response text if it's not JSON for debugging
        response_text = ""
        if 'response' in locals() and hasattr(response, 'text'):
            response_text = response.text[:200]  # Log first 200 chars
        raise ValueError(f"Invalid JSON response from HubSpot. Response text (partial): {response_text}") from jerr


# --- FastAPI Application ---
app = FastAPI(
    title="HubSpot Availability API",
    description="Provides meeting availability slots from HubSpot, transformed into a user-friendly format.",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    # Optional: Check for HUBSPOT_API_KEY at startup to fail fast
    if not os.getenv("HUBSPOT_API_KEY"):
        print("FATAL: HUBSPOT_API_KEY environment variable not set. Application cannot function correctly.")
        # For a real deployment, you might exit here or have a health check fail
    print("Application startup: HubSpot Availability API is ready.")
    print(f"Default business hours filter (if applied): 9 AM - 5 PM, Mon-Fri.")


@app.get("/availability",
         response_model=Dict[str, List[str]],
         summary="Get Meeting Availability",
         description="Fetches availability for a HubSpot meeting link slug and returns formatted slots for the specified timezone."
         )
async def get_availability_endpoint(
        slug: str = Query(..., min_length=1, description="The meeting link slug from HubSpot."),
        timezone: str = Query("America/Mexico_City",
                              description="Target timezone for displaying slots (e.g., 'America/New_York', 'Europe/London'). Must be an IANA timezone database name."),
        apply_business_hours_filter: Optional[bool] = Query(False,
                                                            description="Apply an additional server-side business hours filter (default: 9AM-5PM, Mon-Fri).")
):
    HUBSPOT_API_KEY_from_env = os.getenv("HUBSPOT_API_KEY")
    if not HUBSPOT_API_KEY_from_env:
        raise HTTPException(status_code=500,
                            detail="Server configuration error: HUBSPOT_API_KEY not set.")

    # Validate timezone early
    try:
        pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise HTTPException(status_code=400,
                            detail=f"Invalid timezone provided: '{timezone}'. Please use a valid IANA timezone name.")

    try:
        hubspot_data = fetch_hubspot_meeting_availability(HUBSPOT_API_KEY_from_env, slug, timezone)

        transformed_data = process_hubspot_availability(
            hubspot_data,
            timezone,
            apply_business_hours_filter
            # To make business hours configurable via API, add params here:
            # business_start_hour=custom_start_hour_param,
            # business_end_hour=custom_end_hour_param
        )

        # If transformed_data is empty (no slots available or all filtered out),
        # FastAPI will correctly return an empty JSON object {} based on the response_model.
        return transformed_data

    except requests.exceptions.HTTPError as e:
        # Handle errors from HubSpot API (re-raised by fetch_hubspot_meeting_availability)
        status_code = e.response.status_code
        detail_message = f"Error from HubSpot API: Status {status_code} - {e.response.text[:200]}"  # Limit error text length

        if status_code == 401 or status_code == 403:  # Unauthorized or Forbidden
            # This is likely an issue with the HUBSPOT_API_KEY stored on our server
            print(
                f"HubSpot API Authentication Error (Status {status_code}): Check server's HUBSPOT_API_KEY. Response: {e.response.text[:200]}")
            raise HTTPException(status_code=500,
                                detail="HubSpot API authentication error. Please contact administrator.")
        elif status_code == 404:  # Slug not found
            raise HTTPException(status_code=404, detail=f"Meeting slug '{slug}' not found on HubSpot.")
        else:  # Other HubSpot errors (e.g., 400 Bad Request to HubSpot, 5xx from HubSpot)
            # We might treat these as a gateway error or pass through the status.
            # Passing through a generic 502 might be safer for unexpected upstream errors.
            print(f"Unhandled HubSpot API HTTP Error (Status {status_code}): {e.response.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Upstream error from HubSpot: {status_code}")

    except (ConnectionError, TimeoutError) as e:  # Network issues or timeouts connecting to HubSpot
        print(f"Connectivity issue with HubSpot: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: Could not connect to HubSpot. {e}")

    except ValueError as ve:  # Includes JSONDecodeError from fetch, or errors from process_hubspot_availability
        print(f"Data processing or input error: {ve}")
        raise HTTPException(status_code=400, detail=f"Data processing error or invalid input: {ve}")

    except Exception as e:
        # Catch-all for other unexpected errors
        print(f"An unexpected error occurred in /availability endpoint: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail="An unexpected internal server error occurred.")


# --- How to Run ---
# 1. Save this code as `main.py` (or another name like `app.py`).
# 2. Install dependencies:
#    pip install fastapi "uvicorn[standard]" requests pytz
# 3. Set the HubSpot API Key environment variable:
#    Linux/macOS: export HUBSPOT_API_KEY="your_actual_hubspot_HUBSPOT_API_KEY"
#    Windows CMD: set HUBSPOT_API_KEY="your_actual_hubspot_HUBSPOT_API_KEY"
#    Windows PowerShell: $env:HUBSPOT_API_KEY="your_actual_hubspot_HUBSPOT_API_KEY"
# 4. Run the FastAPI application using Uvicorn:
#    uvicorn main:app --reload
#    (Replace `main` with your Python filename if you named it differently).
# 5. Access the API:
#    - Endpoint: http://127.0.0.1:8000/availability?slug=your_slug&timezone=America/New_York
#    - Interactive API docs (Swagger UI): http://127.0.0.1:8000/docs
#    - Alternative API docs (ReDoc): http://127.0.0.1:8000/redoc

if __name__ == "__main__":
    # This block allows running with `python main.py` if uvicorn is installed,
    # but `uvicorn main:app --reload` is the recommended way for development.
    import uvicorn

    print("Attempting to run with Uvicorn. For development, prefer 'uvicorn main:app --reload'")
    uvicorn.run(app, host="127.0.0.1", port=8000)
