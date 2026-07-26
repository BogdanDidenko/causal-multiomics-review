from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import certifi


class ProviderError(RuntimeError):
    def __init__(self, message: str, raw_response: Any | None = None) -> None:
        self.raw_response = raw_response
        super().__init__(message)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 180,
        temperature: float = 0.0,
        top_p: float = 1.0,
        seed: int = 0,
        n: int = 1,
        max_tokens: int | None = None,
        response_format: str = "json_object",
        api_protocol: str = "chat_completions",
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
    ) -> None:
        if api_protocol not in {"chat_completions", "openai_responses"}:
            raise ValueError(f"Unsupported API protocol: {api_protocol}")
        self.api_protocol = api_protocol
        endpoint = "/responses" if api_protocol == "openai_responses" else "/chat/completions"
        self.url = base_url.rstrip("/") + endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed
        self.n = n
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.reasoning_effort = reasoning_effort
        self.text_verbosity = text_verbosity

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        schema_name: str = "screening_response",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = self._request_payload(prompt, schema, schema_name)
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=ssl.create_default_context(cafile=certifi.where()),
            ) as response:
                raw = json.loads(response.read())
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            raise ProviderError(
                f"HTTP {error.code}: {body[:1000]}", raw_response=body
            ) from error
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            raise ProviderError(str(error)) from error

        try:
            content = (
                _responses_output_text(raw)
                if self.api_protocol == "openai_responses"
                else raw["choices"][0]["message"]["content"]
            )
            parsed = json.loads(_strip_code_fence(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderError(
                f"Invalid provider response: {error}", raw_response=raw
            ) from error
        if not isinstance(parsed, dict):
            raise ProviderError("Model response is not a JSON object", raw_response=raw)
        return parsed, raw

    def _request_payload(
        self,
        prompt: str,
        schema: dict[str, Any] | None,
        schema_name: str,
    ) -> dict[str, Any]:
        if self.api_protocol == "openai_responses":
            return self._responses_payload(prompt, schema, schema_name)
        return self._chat_completions_payload(prompt, schema, schema_name)

    def _chat_completions_payload(
        self,
        prompt: str,
        schema: dict[str, Any] | None,
        schema_name: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed,
            "n": self.n,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.response_format == "json_schema" and schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            }
        else:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _responses_payload(
        self,
        prompt: str,
        schema: dict[str, Any] | None,
        schema_name: str,
    ) -> dict[str, Any]:
        text: dict[str, Any] = {}
        if self.text_verbosity is not None:
            text["verbosity"] = self.text_verbosity
        if self.response_format == "json_schema" and schema is not None:
            text["format"] = {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        else:
            text["format"] = {"type": "json_object"}
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": prompt}],
            "text": text,
        }
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.max_tokens is not None:
            payload["max_output_tokens"] = self.max_tokens
        return payload


class CodexCliProvider:
    """Run a schema-constrained reviewer through an isolated Codex CLI process."""

    api_protocol = "codex_cli"
    url = "codex://local/exec"
    temperature = None
    top_p = None
    seed = None
    n = 1
    text_verbosity = None

    def __init__(
        self,
        model: str,
        *,
        codex_bin: str = "codex",
        timeout: int = 900,
        reasoning_effort: str = "medium",
        context_window: int = 32768,
        sandbox: str = "read-only",
        approval_policy: str = "never",
        ephemeral: bool = True,
        ignore_user_config: bool = True,
        ignore_rules: bool = True,
        isolated_home: bool = True,
        auth_path: str | Path | None = None,
        required_cli_version: str | None = None,
        codex_version: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.model = model
        self.codex_bin = codex_bin
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.context_window = context_window
        self.sandbox = sandbox
        self.approval_policy = approval_policy
        self.ephemeral = ephemeral
        self.ignore_user_config = ignore_user_config
        self.ignore_rules = ignore_rules
        self.isolated_home = isolated_home
        self.auth_path = Path(auth_path).expanduser() if auth_path else None
        self.codex_version = codex_version or _read_codex_version(codex_bin, timeout)
        if required_cli_version and self.codex_version != required_cli_version:
            raise ProviderError(
                f"Codex CLI version {self.codex_version!r} does not match "
                f"required version {required_cli_version!r}"
            )
        self.max_tokens = max_tokens
        self.response_format = "json_schema"

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        schema_name: str = "screening_response",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if schema is None:
            raise ValueError("Codex CLI screening requires a JSON Schema")

        with tempfile.TemporaryDirectory(prefix="causal-multiomics-codex-") as directory:
            workdir = Path(directory)
            schema_path = workdir / f"{schema_name}.schema.json"
            output_path = workdir / "last_message.json"
            schema_path.write_text(
                json.dumps(_codex_output_schema(schema), ensure_ascii=False),
                encoding="utf-8",
            )
            command = [
                self.codex_bin,
                "exec",
                "-",
                "--model",
                self.model,
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "--config",
                f"model_context_window={self.context_window}",
                "--config",
                f'approval_policy="{self.approval_policy}"',
                "--sandbox",
                self.sandbox,
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
            ]
            if self.ephemeral:
                command.append("--ephemeral")
            if self.ignore_user_config:
                command.append("--ignore-user-config")
            if self.ignore_rules:
                command.append("--ignore-rules")
            environment = None
            if self.isolated_home:
                codex_home = workdir / "codex-home"
                codex_home.mkdir(mode=0o700)
                source_auth = self.auth_path or _default_codex_auth_path()
                if not source_auth.is_file():
                    raise ProviderError(
                        f"Codex authentication file not found: {source_auth}"
                    )
                shutil.copy2(source_auth, codex_home / "auth.json")
                environment = os.environ.copy()
                environment["CODEX_HOME"] = str(codex_home)
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    cwd=workdir,
                    env=environment,
                    timeout=self.timeout,
                    check=False,
                )
            except FileNotFoundError as error:
                raise ProviderError(
                    f"Codex CLI executable not found: {self.codex_bin}"
                ) from error
            except subprocess.TimeoutExpired as error:
                raise ProviderError(
                    f"Codex CLI timed out after {self.timeout} seconds",
                    raw_response={
                        "transport": self.api_protocol,
                        "stdout": _as_text(error.stdout),
                        "stderr": _as_text(error.stderr),
                    },
                ) from error
            except OSError as error:
                raise ProviderError(f"Codex CLI execution failed: {error}") from error

            raw = {
                "transport": self.api_protocol,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            if completed.returncode:
                raise ProviderError(
                    f"Codex CLI exited with {completed.returncode}: "
                    f"{completed.stderr.strip()[:1000]}",
                    raw_response=raw,
                )
            try:
                content = output_path.read_text(encoding="utf-8")
            except OSError as error:
                raise ProviderError(
                    "Codex CLI completed without a final message", raw_response=raw
                ) from error
            raw["last_message"] = content
            try:
                parsed = json.loads(_strip_code_fence(content))
            except json.JSONDecodeError as error:
                raise ProviderError(
                    f"Invalid Codex CLI JSON response: {error}", raw_response=raw
                ) from error
            if not isinstance(parsed, dict):
                raise ProviderError("Model response is not a JSON object", raw_response=raw)
            return parsed, raw

def _strip_code_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _codex_output_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _codex_output_schema(item)
            for key, item in value.items()
            if key != "uniqueItems"
        }
    if isinstance(value, list):
        return [_codex_output_schema(item) for item in value]
    return value


def _default_codex_auth_path() -> Path:
    configured_home = os.environ.get("CODEX_HOME")
    codex_home = Path(configured_home).expanduser() if configured_home else Path.home() / ".codex"
    return codex_home / "auth.json"


def _read_codex_version(codex_bin: str, timeout: int) -> str:
    try:
        completed = subprocess.run(
            [codex_bin, "--version"],
            text=True,
            capture_output=True,
            timeout=min(timeout, 30),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProviderError(f"Could not determine Codex CLI version: {error}") from error
    if completed.returncode:
        raise ProviderError(
            f"Could not determine Codex CLI version: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _as_text(value: str | bytes | None) -> str | None:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _responses_output_text(raw: dict[str, Any]) -> str:
    output_text = raw.get("output_text")
    if isinstance(output_text, str):
        return output_text
    texts: list[str] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    texts.append(text)
    if not texts:
        raise KeyError("Response contains no output_text")
    return "".join(texts)
