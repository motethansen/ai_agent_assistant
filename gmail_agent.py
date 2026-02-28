import os.path
import json
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
# We need Gmail readonly to see emails and filters
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.readonly'
]

FILTERS_FILE = "gmail_filters.json"

def get_gmail_service():
    """Shows basic usage of the Gmail API."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: 'credentials.json' not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

def get_snoozed_emails(service):
    """
    Fetches emails that are currently snoozed.
    Note: Gmail search 'is:snoozed' can find these.
    """
    if not service:
        return []

    try:
        # Search for snoozed emails
        results = service.users().messages().list(userId='me', q='is:snoozed').execute()
        messages = results.get('messages', [])
        
        email_list = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            from_email = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            
            email_list.append({
                'id': msg['id'],
                'subject': subject,
                'from': from_email,
                'snippet': msg_data.get('snippet', ''),
                'type': 'snoozed'
            })
        return email_list
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def get_filtered_emails(service, queries):
    """
    Fetches emails matching specific search queries.
    """
    if not service or not queries:
        return []

    all_filtered = []
    try:
        for query in queries:
            results = service.users().messages().list(userId='me', q=query).execute()
            messages = results.get('messages', [])
            
            for msg in messages[:5]:  # Limit to top 5 per filter for brevity
                msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                headers = msg_data.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                from_email = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                
                all_filtered.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': from_email,
                    'snippet': msg_data.get('snippet', ''),
                    'filter': query,
                    'type': 'filtered'
                })
        return all_filtered
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def load_filters():
    """Loads filters from the JSON file."""
    if os.path.exists(FILTERS_FILE):
        with open(FILTERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_filters(filters):
    """Saves filters to the JSON file."""
    with open(FILTERS_FILE, 'w') as f:
        json.dump(filters, f, indent=4)

def add_filter(query):
    """Adds a new filter query."""
    filters = load_filters()
    if query not in filters:
        filters.append(query)
        save_filters(filters)
        return True
    return False

def remove_filter(query):
    """Removes a filter query."""
    filters = load_filters()
    if query in filters:
        filters.remove(query)
        save_filters(filters)
        return True
    return False

if __name__ == '__main__':
    service = get_gmail_service()
    if service:
        print("Snoozed Emails:")
        snoozed = get_snoozed_emails(service)
        for e in snoozed:
            print(f"- {e['subject']} (From: {e['from']})")
        
        filters = load_filters()
        if filters:
            print("\nFiltered Emails:")
            filtered = get_filtered_emails(service, filters)
            for e in filtered:
                print(f"- [{e['filter']}] {e['subject']} (From: {e['from']})")
