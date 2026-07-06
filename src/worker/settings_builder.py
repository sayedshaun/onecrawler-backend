"""Maps the JSON payload stored on a CrawlJob (mirroring the UI's
ui/src/lib/api-mapper.ts snake_case shape) onto real onecrawler.Settings /
FilterChain objects."""

import re
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel, create_model
from sqlalchemy.ext.asyncio import AsyncSession

from onecrawler import (
    BrowserSettings,
    GenerativeAISettings,
    HumanBehaviorSettings,
    ProxySettings,
    Settings,
)
from onecrawler.filters.chain import AND, OR
from onecrawler.filters import (
    by_date,
    by_extension,
    by_files,
    by_keywords,
    by_cosine_similarity,
)

from src.api.v1.crawler.schema import CrawlSettingsIn, FilterGroupIn
from src.api.v1.settings import crud as settings_crud

_BASE_TYPES: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list[str]": list[str],
}

_OPTIONAL_RE = re.compile(r"^Optional\[(.+)\]$")


def _parse_field_type(type_str: str) -> tuple[Any, Any]:
    match = _OPTIONAL_RE.match(type_str)
    if match:
        py_type = _BASE_TYPES.get(match.group(1), str)
        return Optional[py_type], None
    py_type = _BASE_TYPES.get(type_str, str)
    return py_type, ...


def build_output_schema(fields: dict[str, str]) -> Optional[Type[BaseModel]]:
    if not fields:
        return None
    field_defs = {
        name: _parse_field_type(type_str) for name, type_str in fields.items()
    }
    return create_model("GenAIOutputSchema", **field_defs)


async def build_settings(db: AsyncSession, payload: dict) -> Settings:
    s = CrawlSettingsIn(**payload)

    proxies = (
        [ProxySettings(**p.model_dump()) for p in s.proxies] if s.proxies else None
    )

    genai = None
    if s.genai:
        api_key = s.genai.api_key or await settings_crud.get_api_key_value(
            db, s.genai.provider
        )
        genai = GenerativeAISettings(
            provider=s.genai.provider,
            model_name=s.genai.model_name,
            api_key=api_key,
            output_schema=build_output_schema(s.genai.output_schema),
            base_url=s.genai.base_url,
            timeout=s.genai.timeout,
        )

    browser_kwargs: dict[str, Any] = dict(
        viewport={
            "width": s.browser_settings.viewport.width,
            "height": s.browser_settings.viewport.height,
        },
        locale=s.browser_settings.locale,
        timezone_id=s.browser_settings.timezone_id,
        headless=s.browser_settings.headless,
        wait_until=s.browser_settings.wait_until,
        timeout=s.browser_settings.timeout,
    )
    if s.browser_settings.user_agent:
        browser_kwargs["user_agent"] = s.browser_settings.user_agent

    human_behavior = (
        HumanBehaviorSettings(
            min_delay=s.human_behavior_settings.min_delay,
            max_delay=s.human_behavior_settings.max_delay,
            max_scrolls=s.human_behavior_settings.max_scrolls,
            min_mouse_moves=s.human_behavior_settings.min_mouse_moves,
            max_mouse_moves=s.human_behavior_settings.max_mouse_moves,
        )
        if s.human_behavior_settings
        else HumanBehaviorSettings()
    )

    return Settings(
        verbose=False,
        link_extraction_strategy=s.link_extraction_strategy,
        link_extraction_limit=s.link_extraction_limit,
        include_link_patterns=s.include_link_patterns,
        exclude_link_patterns=s.exclude_link_patterns,
        scraping_strategy=s.scraping_strategy,
        scraping_output_format=s.scraping_output_format,
        genai=genai,
        concurrency=s.concurrency,
        max_retries=s.max_retries,
        request_timeout=s.request_timeout,
        retry_delay=s.retry_delay,
        proxies=proxies,
        proxy_rotation_method=s.proxy_rotation_method,
        browser_settings=BrowserSettings(**browser_kwargs),
        show_progress=False,
        enable_logging=False,
        enable_human_behaviors=s.enable_human_behaviors,
        human_behavior_settings=human_behavior,
    )


def build_filter_chain(filters: Optional[dict]) -> Optional[Callable[[dict], bool]]:
    if not filters:
        return None

    group = FilterGroupIn(**filters)
    if not group.chain:
        return None

    predicates: list[Callable[[dict], bool]] = []
    for node in group.chain:
        if node.kind == "by_date":
            predicates.append(by_date(start=node.start, end=node.end))
        elif node.kind == "by_keywords":
            predicates.append(by_keywords(node.keywords or []))
        elif node.kind == "by_files":
            predicates.append(by_files(node.types or []))
        elif node.kind == "by_extension":
            predicates.append(by_extension(node.extensions or []))
        elif node.kind == "by_cosine_similarity":
            predicates.append(
                by_cosine_similarity(node.query or "", node.threshold or 0.25)
            )

    if not predicates:
        return None

    return AND(*predicates) if group.mode == "AND" else OR(*predicates)
