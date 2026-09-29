import uuid
from datetime import datetime, timedelta

from googleapiclient.discovery import build

from auth import get_credentials


def _service(account: str):
    return build("calendar", "v3", credentials=get_credentials(account))


def list_events(account: str, days_ahead: int = 7, max_results: int = 20,
                 start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    svc = _service(account)
    if start_date is not None:
        time_min = start_date if "T" in start_date else start_date + "T00:00:00Z"
    else:
        time_min = datetime.utcnow().isoformat() + "Z"

    if end_date is not None:
        time_max = end_date if "T" in end_date else end_date + "T23:59:59Z"
    else:
        base = datetime.fromisoformat(time_min.replace("Z", "")) if start_date else datetime.utcnow()
        time_max = (base + timedelta(days=days_ahead)).isoformat() + "Z"

    result = svc.events().list(
        calendarId="primary", timeMin=time_min, timeMax=time_max,
        maxResults=max_results, singleEvents=True, orderBy="startTime"
    ).execute()
    events = []
    for e in result.get("items", []):
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        end = e["end"].get("dateTime", e["end"].get("date", ""))
        events.append({
            "id": e["id"],
            "summary": e.get("summary", "(sin título)"),
            "start": start,
            "end": end,
            "location": e.get("location", ""),
            "description": e.get("description", ""),
            "attendees": [a.get("email", "") for a in e.get("attendees", [])],
        })
    return events

def create_event(account: str, summary: str, start: str, end: str,
                 description: str = "", location: str = "",
                 attendees: list[str] | None = None, add_meet: bool = False) -> dict:
    svc = _service(account)
    event_body = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location
    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]
    if add_meet:
        event_body["conferenceData"] = {
            "createRequest": {"requestId": str(uuid.uuid4()), "conferenceSolutionKey": {"type": "hangoutsMeet"}}
        }
    kwargs = {"calendarId": "primary", "body": event_body, "sendUpdates": "all"}
    if add_meet:
        kwargs["conferenceDataVersion"] = 1
    event = svc.events().insert(**kwargs).execute()
    result = {"id": event["id"], "summary": event.get("summary", ""), "htmlLink": event.get("htmlLink", "")}
    if add_meet:
        result["meetLink"] = event.get("hangoutLink", "")
    return result


def update_event(account: str, event_id: str, summary: str | None = None,
                 start: str | None = None, end: str | None = None,
                 description: str | None = None, location: str | None = None) -> dict:
    svc = _service(account)
    event = svc.events().get(calendarId="primary", eventId=event_id).execute()
    if summary is not None:
        event["summary"] = summary
    if start is not None:
        event["start"] = {"dateTime": start}
    if end is not None:
        event["end"] = {"dateTime": end}
    if description is not None:
        event["description"] = description
    if location is not None:
        event["location"] = location
    updated = svc.events().update(calendarId="primary", eventId=event_id, body=event, sendUpdates="all").execute()
    return {"id": updated["id"], "summary": updated.get("summary", ""), "updated": updated.get("updated", "")}


def delete_event(account: str, event_id: str) -> dict:
    svc = _service(account)
    svc.events().delete(calendarId="primary", eventId=event_id).execute()
    return {"status": "deleted", "id": event_id}
