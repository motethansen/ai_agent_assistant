import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Shows basic usage of the Google Calendar API.
    Lists the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: 'credentials.json' not found. Please download it from Google Cloud Console.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

def get_busy_slots(service, date_str=None):
    """
    Fetches events for the specified date and returns a list of busy time slots.
    date_str should be in 'YYYY-MM-DD' format. Defaults to today.
    """
    if not service:
        return []

    if date_str:
        day = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    else:
        day = datetime.datetime.now()

    # Define the start and end of the day
    start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    end_of_day = day.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + 'Z'

    print(f"Fetching busy slots for {day.date()}...")
    
    events_result = service.events().list(calendarId='primary', timeMin=start_of_day,
                                        timeMax=end_of_day, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])

    busy_slots = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        # Filter out all-day events or format them properly if needed
        if 'T' in start:  # It's a dateTime event
            busy_slots.append({
                'summary': event.get('summary', 'No Title'),
                'start': start,
                'end': end
            })
    
    return busy_slots

def create_events(service, schedule):
    """
    Creates calendar events from a list of scheduled tasks.
    """
    if not service or not schedule:
        return

    print(f"Syncing {len(schedule)} tasks to Google Calendar...")
    for item in schedule:
        event = {
            'summary': f"AI: {item['task']}",
            'start': {'dateTime': item['start']},
            'end': {'dateTime': item['end']},
        }
        try:
            event_result = service.events().insert(calendarId='primary', body=event).execute()
            print(f"Created: {event_result.get('htmlLink')}")
        except Exception as e:
            print(f"Error creating event for {item['task']}: {e}")

if __name__ == '__main__':
    service = get_calendar_service()
    if service:
        slots = get_busy_slots(service)
        for slot in slots:
            print(f"BUSY: {slot['summary']} ({slot['start']} to {slot['end']})")
