import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


def _service(access_token: str):
    creds = Credentials(token=access_token)
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def create_calendar_event(
    summary: str,
    description: str,
    start_time_iso: str,
    end_time_iso: str,
    timezone: str = "Asia/Kolkata",
    access_token: str = None,
    color_id: str | None = None,
) -> tuple[str, str] | tuple[None, None]:
    """
    Creates an event on the user's primary calendar using their access token.
    Returns (htmlLink, event_id) on success, (None, None) on failure.
    """
    if not access_token:
        logger.warning("No user access token provided. Skipping Calendar sync.")
        return None, None

    event_body = {
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
        'source': {'title': 'Notschool', 'url': 'https://notschool.app'},
    }
    if color_id:
        event_body['colorId'] = color_id

    try:
        service = _service(access_token)
        created = service.events().insert(
            calendarId='primary',
            body=event_body,
            sendUpdates='none',
        ).execute()
        return created.get('htmlLink'), created.get('id')
    except HttpError as e:
        # Surface the *reason* — most "events aren't being scheduled" reports come
        # from a missing calendar scope or an expired token.
        logger.error("Calendar API HttpError [%s]: %s", e.resp.status if e.resp else "?", e)
        return None, None
    except Exception as e:
        logger.error("Calendar API Error: %s", e, exc_info=True)
        return None, None


def delete_calendar_event(event_id: str, access_token: str) -> bool:
    """Deletes a calendar event by ID. Idempotent: 404/410 count as success."""
    if not access_token or not event_id:
        return False
    try:
        service = _service(access_token)
        service.events().delete(
            calendarId='primary',
            eventId=event_id,
            sendUpdates='none',
        ).execute()
        return True
    except HttpError as e:
        status = e.resp.status if e.resp else None
        if status in (404, 410):
            # Already gone — treat as success so callers can stop tracking it.
            return True
        logger.error("Calendar Delete Error (event %s): %s", event_id, e)
        return False
    except Exception as e:
        logger.error("Calendar Delete Error (event %s): %s", event_id, e)
        return False


def update_calendar_event(
    event_id: str,
    summary: str,
    description: str,
    start_time_iso: str,
    end_time_iso: str,
    timezone: str,
    access_token: str,
) -> tuple[str | None, str | None]:
    """Patch an existing event in place. Returns (htmlLink, event_id) or (None, None)."""
    if not access_token or not event_id:
        return None, None
    try:
        service = _service(access_token)
        body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time_iso, 'timeZone': timezone},
            'end': {'dateTime': end_time_iso, 'timeZone': timezone},
        }
        updated = service.events().patch(
            calendarId='primary',
            eventId=event_id,
            body=body,
            sendUpdates='none',
        ).execute()
        return updated.get('htmlLink'), updated.get('id')
    except HttpError as e:
        status = e.resp.status if e.resp else None
        if status in (404, 410):
            return None, None
        logger.error("Calendar Update Error (event %s): %s", event_id, e)
        return None, None
    except Exception as e:
        logger.error("Calendar Update Error (event %s): %s", event_id, e)
        return None, None
