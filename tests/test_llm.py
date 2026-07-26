import json
import subprocess
from pathlib import Path

from causal_multiomics_review.llm import (
    CodexCliProvider,
    OpenAICompatibleProvider,
    _responses_output_text,
)


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


def test_codex_cli_provider_fixes_terra_medium_and_enforces_schema(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["prompt"] = kwargs["input"]
        schema_path = Path(command[command.index("--output-schema") + 1])
        output_path = Path(command[command.index("--output-last-message") + 1])
        captured["schema"] = json.loads(schema_path.read_text())
        output_path.write_text('{"decision": "include"}')
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("causal_multiomics_review.llm.subprocess.run", fake_run)
    provider = CodexCliProvider("gpt-5.6-terra", timeout=123, max_tokens=4000)
    answer, raw = provider.complete_json(
        "Return the screening decision.",
        {"type": "object", "properties": {"decision": {"type": "string"}}},
        "scope_reviewer",
    )

    command = captured["command"]
    assert command[:3] == ["codex", "exec", "-"]
    assert command[command.index("--model") + 1] == "gpt-5.6-terra"
    assert command[command.index("--config") + 1] == 'model_reasoning_effort="medium"'
    context_config = command.index("--config", command.index("--config") + 1)
    assert command[context_config + 1] == "model_context_window=32768"
    approval_config = command.index("--config", context_config + 1)
    assert command[approval_config + 1] == 'approval_policy="never"'
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert captured["prompt"] == "Return the screening decision."
    assert captured["schema"] == {
        "type": "object",
        "properties": {"decision": {"type": "string"}},
    }
    assert answer == {"decision": "include"}
    assert raw["transport"] == "codex_cli"
