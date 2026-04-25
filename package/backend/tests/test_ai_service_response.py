from app.services.ai_service import extract_completion_content


def test_extract_completion_content_accepts_plain_string_gateway_response():
    assert extract_completion_content("rewritten text") == "rewritten text"


def test_extract_completion_content_accepts_openai_compatible_dict():
    response = {"choices": [{"message": {"content": "rewritten text"}}]}

    assert extract_completion_content(response) == "rewritten text"
