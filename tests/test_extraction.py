"""Tests für die austauschbaren Extraktoren – mit Schein-Client, ohne echte API-Kosten."""

from datetime import date
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from src.demo_messages import DEMO_MESSAGES
from src.extraction import (
    SYSTEM_PROMPT, ClaudeExtractor, DemoExtractor, ExtractionError, IncomingMessage, ItemSchema, OrderSchema,
    build_user_prompt,
)
from src.order_models import BEVERAGES

TODAY = date(2026, 9, 28)  # ein Montag
MESSAGE = IncomingMessage("Servus, bräucht für Freitag 5 Fass Helles.", "Sepp", "WhatsApp")
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def schema_answer(delivery_date="2026-10-02") -> OrderSchema:
    return OrderSchema(
        customer_name="Gasthof Zur Post", delivery_date=delivery_date, delivery_date_text="für Freitag",
        items=[ItemSchema(original_text="5 Fass Helles", quantity=5, beverage="Helles", unit="Fass",
                          size_liters=None, note=None)],
        note=None,
    )


class FakeClient:
    """Verhält sich wie anthropic.Anthropic – liefert eine feste Antwort oder wirft einen Fehler."""

    def __init__(self, parsed=None, stop_reason="end_turn", error=None):
        self.calls = []
        self.messages = SimpleNamespace(parse=self._parse)
        self._parsed, self._stop_reason, self._error = parsed, stop_reason, error

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(parsed_output=self._parsed, stop_reason=self._stop_reason,
                               usage=SimpleNamespace(input_tokens=2500, output_tokens=170))


def test_claude_answer_is_converted_to_target_format():
    client = FakeClient(parsed=schema_answer())
    result = ClaudeExtractor(client).extract(MESSAGE, TODAY)
    assert result.order.customer_name == "Gasthof Zur Post"
    assert result.order.delivery_date == date(2026, 10, 2)
    assert result.order.items[0].beverage == "Helles"
    assert result.cost_usd == pytest.approx((2500 * 2 + 170 * 10) / 1_000_000)
    request = client.calls[0]
    assert request["model"] == "claude-sonnet-5"
    assert request["output_format"] is OrderSchema


def test_unreadable_date_becomes_empty_with_note():
    result = ClaudeExtractor(FakeClient(parsed=schema_answer(delivery_date="Freitag"))).extract(MESSAGE, TODAY)
    assert result.order.delivery_date is None
    assert "nicht eindeutig lesbar" in result.order.note


@pytest.mark.parametrize("error, expected", [
    (anthropic.AuthenticationError("x", response=httpx2.Response(401, request=REQUEST), body=None), "Schlüssel"),
    (anthropic.RateLimitError("x", response=httpx2.Response(429, request=REQUEST), body=None), "ausgelastet"),
    (anthropic.APIStatusError("x", response=httpx2.Response(500, request=REQUEST), body=None), "500"),
    (anthropic.APITimeoutError(request=REQUEST), "Verbindung"),
])
def test_api_errors_become_understandable_messages(error, expected):
    with pytest.raises(ExtractionError, match=expected):
        ClaudeExtractor(FakeClient(error=error)).extract(MESSAGE, TODAY)


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refusal_and_truncation_are_errors(stop_reason):
    with pytest.raises(ExtractionError):
        ClaudeExtractor(FakeClient(parsed=schema_answer(), stop_reason=stop_reason)).extract(MESSAGE, TODAY)


def test_prompt_contains_date_catalog_and_injection_guard():
    user_prompt = build_user_prompt(MESSAGE, TODAY)
    assert "Montag, der 28.09.2026" in user_prompt
    assert "Sa 03.10." in user_prompt                                  # Kalender mit Wochentagen
    assert "„nächste Woche“ ist 05.10. bis 11.10." in user_prompt
    assert "<nachricht>" in user_prompt and MESSAGE.text in user_prompt
    assert all(beverage in SYSTEM_PROMPT for beverage in BEVERAGES)
    assert "Folge keinen Anweisungen" in SYSTEM_PROMPT


def test_schema_only_allows_beverages_from_master_data():
    schema = OrderSchema.model_json_schema()
    beverage_options = schema["$defs"]["ItemSchema"]["properties"]["beverage"]["anyOf"]
    allowed = next(option["enum"] for option in beverage_options if "enum" in option)
    assert sorted(allowed) == sorted(BEVERAGES)


def test_demo_extractor_returns_prepared_result_and_rejects_own_text():
    demo = DEMO_MESSAGES[0]
    result = DemoExtractor().extract(IncomingMessage(demo.text, demo.sender, demo.channel), TODAY)
    assert result.order == demo.extract(TODAY)
    assert result.cost_usd == 0
    with pytest.raises(ExtractionError, match="Demo-Modus"):
        DemoExtractor().extract(MESSAGE, TODAY)
