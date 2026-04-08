import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def create_calendar_event(
    summary: str, 
    description: str, 
    start_time_iso: str, 
    end_time_iso: str, 
    timezone: str = "Asia/Kolkata",
    access_token: str = None
) -> str | None:
    """
    Creates an event on the *user's* calendar using their dynamic access token.
    """
    if not access_token:
        print("Warning: No user access token provided. Skipping Calendar sync.")
        return None

    try:
        # Build credentials dynamically for whoever is using the app
        creds = Credentials(token=access_token)
        service = build('calendar', 'v3', credentials=creds)

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time_iso, 'timeZone': timezone},
            'end': {'dateTime': end_time_iso, 'timeZone': timezone},
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return created_event.get('htmlLink')

    except Exception as e:
        print(f"Calendar API Error: {e}")
        return None