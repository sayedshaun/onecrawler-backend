"""Guards against field-name drift between onecrawler-ui and the request schemas.

Every request schema inherits `InSchema`, which sets `extra="ignore"` — so a field the
UI sends that the backend does not declare is dropped in silence: no 422, no warning,
and the setting simply never takes effect. `scraping_output_format` shipped that way.
`extra="ignore"` stays (a live client must never start 422-ing on an extra field), so
these lists are the thing that turns such drift into a failing test.

Keep them in sync with `buildSettingsPayload` in onecrawler-ui/src/lib/api-mapper.ts.
"""

import pytest
from pydantic import BaseModel, ValidationError

from src.api.v1.crawler.schema import (
    BrowserSettingsIn,
    CrawlSettingsIn,
    CreateCrawlRequest,
    FilterGroupIn,
    FilterNodeIn,
    GenAISettingsIn,
    HumanBehaviorSettingsIn,
    ProxySettingsIn,
    ViewportIn,
)

# Every key buildSettingsPayload puts on the wire, per object it nests them under.
UI_PAYLOAD_FIELDS: list[tuple[type[BaseModel], set[str]]] = [
    (
        CreateCrawlRequest,
        {"target_url", "mode", "settings", "filters"},
    ),
    (
        CrawlSettingsIn,
        {
            "link_extraction_strategy",
            "link_extraction_limit",
            "include_link_patterns",
            "exclude_link_patterns",
            "scraping_strategy",
            "scraping_output_format",
            "genai",
            "concurrency",
            "max_retries",
            "request_timeout",
            "retry_delay",
            "proxies",
            "proxy_rotation_method",
            "browser_settings",
            "enable_human_behaviors",
            "human_behavior_settings",
        },
    ),
    (
        BrowserSettingsIn,
        {
            "viewport",
            "locale",
            "timezone_id",
            "user_agent",
            "headless",
            "wait_until",
            "timeout",
        },
    ),
    (ViewportIn, {"width", "height"}),
    (
        GenAISettingsIn,
        {"provider", "model_name", "api_key", "base_url", "timeout", "output_schema"},
    ),
    (ProxySettingsIn, {"server", "username", "password"}),
    (
        HumanBehaviorSettingsIn,
        {
            "min_delay",
            "max_delay",
            "max_scrolls",
            "min_mouse_moves",
            "max_mouse_moves",
        },
    ),
    (FilterGroupIn, {"mode", "chain"}),
    (
        FilterNodeIn,
        {
            "kind",
            "start",
            "end",
            "keywords",
            "types",
            "extensions",
            "query",
            "threshold",
        },
    ),
]


@pytest.mark.parametrize(
    ("model", "ui_fields"), UI_PAYLOAD_FIELDS, ids=lambda v: getattr(v, "__name__", "")
)
def test_every_ui_field_is_declared_on_the_schema(
    model: type[BaseModel], ui_fields: set[str]
) -> None:
    undeclared = ui_fields - set(model.model_fields)
    assert not undeclared, (
        f"{model.__name__} does not declare {sorted(undeclared)}, so extra='ignore' "
        f"drops it silently. Add the field, or stop sending it from the UI."
    )


def test_unknown_settings_field_is_dropped_without_error() -> None:
    """The behaviour the lists above exist to compensate for."""
    settings = CrawlSettingsIn.model_validate(
        {
            "browser_settings": {"viewport": {"width": 1280, "height": 800}},
            "not_a_real_field": "ignored",
        }
    )
    assert not hasattr(settings, "not_a_real_field")


def test_scraping_output_format_defaults_to_json() -> None:
    """Clients that omit the field keep the previous hardcoded behaviour."""
    settings = CrawlSettingsIn.model_validate(
        {"browser_settings": {"viewport": {"width": 1280, "height": 800}}}
    )
    assert settings.scraping_output_format == "json"


@pytest.mark.parametrize(
    ("sent", "stored"),
    [
        ("prothomalo.com", "https://prothomalo.com"),
        ("  example.com/blog  ", "https://example.com/blog"),
        ("http://example.com", "http://example.com"),
        ("https://example.com", "https://example.com"),
    ],
)
def test_target_url_gets_a_scheme(sent: str, stored: str) -> None:
    """Playwright can't navigate a schemeless URL — one is normalized on the way in."""
    request = CreateCrawlRequest.model_validate(
        {
            "target_url": sent,
            "mode": "crawler",
            "settings": {"browser_settings": {"viewport": {"width": 1, "height": 1}}},
        }
    )
    assert request.target_url == stored


@pytest.mark.parametrize("sent", ["", "   ", "ftp://example.com", "https://"])
def test_unusable_target_url_is_rejected(sent: str) -> None:
    with pytest.raises(ValidationError):
        CreateCrawlRequest.model_validate(
            {
                "target_url": sent,
                "mode": "crawler",
                "settings": {
                    "browser_settings": {"viewport": {"width": 1, "height": 1}}
                },
            }
        )
