import pytest
import json
import ai_orchestration
from ai_orchestration import generate_schedule, VALID_CATEGORIES

def test_ai_schedules_exercise_and_rest(mocker):
    """
    Test that the AI includes mandatory exercise and rest even if not in the backlog.
    """
    mock_response_text = json.dumps({
        "schedule": [
            {"task": "Morning Exercise", "category": "Personal", "start": "2026-02-26T08:00:00Z", "end": "2026-02-26T08:30:00Z"},
            {"task": "Rest/Meditation", "category": "Personal", "start": "2026-02-26T13:00:00Z", "end": "2026-02-26T13:30:00Z"}
        ],
        "suggestions": []
    })
    
    # Create a mock for the response object
    mock_response = mocker.Mock()
    mock_response.text = mock_response_text
    
    # Mock the Client and the generate_content call
    mock_client = mocker.Mock()
    mocker.patch("ai_orchestration.genai.Client", return_value=mock_client)
    mock_client.models.generate_content.return_value = mock_response
    
    tasks = [{"task": "Work on Book", "category": "Ref.team Book editing", "source": "Obsidian"}]
    busy = []
    
    result = generate_schedule(tasks, busy)
    
    # Verify exercise/rest are in the returned schedule
    task_names = [item['task'].lower() for item in result['schedule']]
    assert any("exercise" in name for name in task_names)
    assert any("rest" in name for name in task_names)

def test_category_mapping_logic(mocker):
    """
    Test that the AI correctly suggests or maps categories.
    """
    mock_response_text = json.dumps({
        "schedule": [],
        "suggestions": [
            {"task": "Buy groceries", "suggested_category": "Personal", "reason": "General household task"}
        ]
    })
    
    mock_response = mocker.Mock()
    mock_response.text = mock_response_text
    
    mock_client = mocker.Mock()
    mocker.patch("ai_orchestration.genai.Client", return_value=mock_client)
    mock_client.models.generate_content.return_value = mock_response
    
    tasks = [{"task": "Buy groceries", "category": "Uncategorized", "source": "Obsidian"}]
    busy = []
    
    result = generate_schedule(tasks, busy)
    
    assert len(result['suggestions']) > 0
    assert result['suggestions'][0]['suggested_category'] == "Personal"

def test_valid_categories_list():
    """
    Verify the static list of categories matches user requirements.
    """
    expected = [
        "Ref.team Book editing", "Ref.team Degree planning", "Ref.team innovation workshop",
        "winedragons", "urbanlife works", "cheers", "personal and vizneo website",
        "learning Thai", "writing academic papers", "budgeting app", "Personal"
    ]
    for cat in expected:
        assert cat in VALID_CATEGORIES
