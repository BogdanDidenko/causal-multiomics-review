from causal_multiomics_review.llm import OpenAICompatibleProvider, _responses_output_text


def test_responses_provider_uses_structured_output_and_reasoning() -> None:
    provider = OpenAICompatibleProvider(
        "https://api.openai.com/v1",
        "test-key",
        "gpt-5.6-luna",
        api_protocol="openai_responses",
        response_format="json_schema",
        reasoning_effort="medium",
        text_verbosity="low",
        max_tokens=4000,
    )
    payload = provider._request_payload("Return JSON", {"type": "object"}, "review")
    assert provider.url == "https://api.openai.com/v1/responses"
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["max_output_tokens"] == 4000
    assert payload["text"]["verbosity"] == "low"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert "temperature" not in payload


def test_responses_output_text_supports_explicit_and_nested_shapes() -> None:
    assert _responses_output_text({"output_text": "{\"ok\": true}"}) == '{"ok": true}'
    assert _responses_output_text(
        {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"ok": true}'}],
                }
            ]
        }
    ) == '{"ok": true}'
