"""Views configure their own widgets for App intents instead of the App reaching into them (ARC-008)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from parllama.messages.model_messages import LocalCreateModelFromExistingRequested
from parllama.widgets.views.create_model_view import ModelCreateView


class _CreateViewApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.view = ModelCreateView()

    def compose(self) -> ComposeResult:
        yield self.view


def _request(model_name: str, quantization_level: str | None = None) -> LocalCreateModelFromExistingRequested:
    return LocalCreateModelFromExistingRequested(
        widget=None,
        model_name=model_name,
        model_from=model_name,
        system_prompt="be terse",
        model_template="{{ .Prompt }}",
        model_license="MIT",
        quantization_level=quantization_level,
    )


@pytest.mark.anyio
async def test_prefill_from_existing_fills_every_field() -> None:
    app = _CreateViewApp()
    async with app.run_test():
        app.view.prefill_from_existing(_request("llama3", "q4_K_M"))

        assert app.view.name_input.value == "my-llama3:latest"
        assert app.view.input_from.value == "llama3"
        assert app.view.ta_system_prompt.text == "be terse"
        assert app.view.ta_template.text == "{{ .Prompt }}"
        assert app.view.ta_license.text == "MIT"
        assert app.view.quantize_input.value == "q4_K_M"


@pytest.mark.anyio
async def test_prefill_keeps_existing_latest_suffix() -> None:
    app = _CreateViewApp()
    async with app.run_test():
        app.view.prefill_from_existing(_request("llama3:latest"))

        assert app.view.name_input.value == "my-llama3:latest"
        assert app.view.quantize_input.value == ""
