import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def create_calendar_event(
    summary: str, 
    description: str, 
    start_time_iso: str, 
    end_time_iso: str, 
    timezone: str = "Asia/Kolkata"
) -> str | None:
    """
    Pure tool function to hit the Google Calendar API.
    Creates an event and returns the event ID or a Google Meet link.
    """
    # For a hackathon, assume token.json is generated via a quickstart script
    if not os.path.exists('token.json'):
        print("Warning: Google Calendar token.json not found.")
        return None

    try:
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/calendar.events'])
        service = build('calendar', 'v3', credentials=creds)

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time_iso,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time_iso,
                'timeZone': timezone,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        # Insert the event into the primary calendar
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return created_event.get('htmlLink')

    except Exception as e:
        print(f"Calendar API Error: {e}")
        return None