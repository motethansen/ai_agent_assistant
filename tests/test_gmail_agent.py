import pytest
from unittest.mock import MagicMock, patch
import gmail_agent

@patch('gmail_agent.os.path.exists')
@patch('gmail_agent.Credentials.from_authorized_user_file')
@patch('gmail_agent.build')
def test_get_gmail_service(mock_build, mock_creds, mock_exists):
    mock_exists.return_value = True
    mock_creds.return_value = MagicMock(valid=True)
    
    service = gmail_agent.get_gmail_service()
    
    assert service is not None
    mock_build.assert_called_with('gmail', 'v1', credentials=mock_creds.return_value)

@patch('gmail_agent.build')
def test_get_snoozed_emails(mock_build):
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        'messages': [{'id': '123'}]
    }
    mock_service.users().messages().get().execute.return_value = {
        'id': '123',
        'snippet': 'This is a snoozed email',
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Snoozed Test'},
                {'name': 'From', 'value': 'test@example.com'}
            ]
        }
    }
    
    emails = gmail_agent.get_snoozed_emails(mock_service)
    
    assert len(emails) == 1
    assert emails[0]['subject'] == 'Snoozed Test'
    assert emails[0]['from'] == 'test@example.com'
    assert emails[0]['type'] == 'snoozed'

@patch('gmail_agent.build')
def test_get_filtered_emails(mock_build):
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        'messages': [{'id': '456'}]
    }
    mock_service.users().messages().get().execute.return_value = {
        'id': '456',
        'snippet': 'This is a filtered email',
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Filtered Test'},
                {'name': 'From', 'value': 'boss@example.com'}
            ]
        }
    }
    
    emails = gmail_agent.get_filtered_emails(mock_service, ['from:boss'])
    
    assert len(emails) == 1
    assert emails[0]['subject'] == 'Filtered Test'
    assert emails[0]['filter'] == 'from:boss'
    assert emails[0]['type'] == 'filtered'

def test_load_save_filters(tmp_path):
    # Mock FILTERS_FILE to use tmp_path
    temp_filters_file = tmp_path / "test_filters.json"
    with patch('gmail_agent.FILTERS_FILE', str(temp_filters_file)):
        filters = ['test filter']
        gmail_agent.save_filters(filters)
        
        loaded = gmail_agent.load_filters()
        assert loaded == filters
        
        gmail_agent.add_filter('new filter')
        assert 'new filter' in gmail_agent.load_filters()
        
        gmail_agent.remove_filter('test filter')
        assert 'test filter' not in gmail_agent.load_filters()
