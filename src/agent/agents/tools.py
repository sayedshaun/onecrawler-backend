import httpx
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..core.client import OneCrawlerClient


def _client(config: RunnableConfig) -> OneCrawlerClient:
    token = config["configurable"]["auth_token"]
    return OneCrawlerClient(token=token)


def _crawl_settings(
    max_pages: int | None,
    concurrency: int | None,
    scraping_strategy: str | None,
    include_link_patterns: list[str] | None,
    exclude_link_patterns: list[str] | None,
    enable_human_behaviors: bool | None = None,
) -> dict:
    """Build a CrawlSettingsIn body. browser_settings.viewport is the only
    field the real API requires with no default, so it's always supplied."""
    settings: dict = {"browser_settings": {"viewport": {"width": 1280, "height": 800}}}
    if max_pages is not None:
        settings["link_extraction_limit"] = max_pages
    if concurrency is not None:
        settings["concurrency"] = concurrency
    if scraping_strategy is not None:
        settings["scraping_strategy"] = scraping_strategy
    if include_link_patterns is not None:
        settings["include_link_patterns"] = include_link_patterns
    if exclude_link_patterns is not None:
        settings["exclude_link_patterns"] = exclude_link_patterns
    if enable_human_behaviors is not None:
        settings["enable_human_behaviors"] = enable_human_behaviors
    return settings


@tool
async def create_crawl(
    target_url: str,
    mode: str = "crawler",
    max_pages: int | None = None,
    concurrency: int | None = None,
    scraping_strategy: str | None = None,
    include_link_patterns: list[str] | None = None,
    exclude_link_patterns: list[str] | None = None,
    enable_human_behaviors: bool | None = None,
    config: RunnableConfig = None,
) -> dict:
    """Start a new crawl job against a URL.

    mode: one of "crawler" (follow links, default), "sitemap" (crawl a sitemap
    URL), "link_extraction" (only collect links, no content), or "scraper"
    (scrape a single given page). max_pages caps how many links are followed
    (link_extraction_limit, default 50 if omitted). scraping_strategy: one of
    "heuristic" (default), "genai", "markdownify". include/exclude_link_patterns
    are fnmatch glob patterns matched against the full URL path, not substrings
    — a bare keyword like "articles" only matches a path that IS exactly
    "articles"; to match any path containing a segment, wrap it in wildcards,
    e.g. "*/articles/*" or "*sports*". (The OpenAPI schema's description of this
    field claims plain keywords get auto-expanded into "/<keyword>/*" — verified
    against the running backend on 2026-07-20 that this is NOT what happens;
    plain keywords match almost nothing, wildcarded globs work as expected.)
    enable_human_behaviors adds human-like delays/mouse movement/scrolling to
    evade bot detection (slower, but harder to block). Don't set fields the
    user didn't ask about — leave them unset for the API's defaults.
    """
    payload = {
        "target_url": target_url,
        "mode": mode,
        "settings": _crawl_settings(
            max_pages,
            concurrency,
            scraping_strategy,
            include_link_patterns,
            exclude_link_patterns,
            enable_human_behaviors,
        ),
    }
    return await _client(config).create_crawl(payload)


@tool
async def list_crawls(
    status: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    config: RunnableConfig = None,
) -> dict:
    """List crawl jobs. status filters by job status, q is a free-text search
    over jobs, limit (max 100, default 20) and offset paginate."""
    params = {
        k: v
        for k, v in {
            "status": status,
            "q": q,
            "limit": limit,
            "offset": offset,
        }.items()
        if v is not None
    }
    return await _client(config).list_crawls(**params)


@tool
async def get_crawl(job_id: str, config: RunnableConfig = None) -> dict:
    """Get the current status and details of a single crawl job."""
    return await _client(config).get_crawl(job_id)


@tool
async def cancel_crawl(job_id: str, config: RunnableConfig = None) -> dict:
    """Cancel a running crawl job."""
    return await _client(config).cancel_crawl(job_id)


@tool
async def retry_crawl(job_id: str, config: RunnableConfig = None) -> dict:
    """Retry a failed or cancelled crawl job."""
    return await _client(config).retry_crawl(job_id)


@tool
async def delete_crawl(job_id: str, config: RunnableConfig = None) -> dict:
    """Delete a crawl job and its associated data."""
    return await _client(config).delete_crawl(job_id)


@tool
async def get_crawl_logs(
    job_id: str,
    limit: int | None = None,
    offset: int | None = None,
    config: RunnableConfig = None,
) -> dict:
    """Get the execution logs for a crawl job. limit (max 200, default 50) and
    offset paginate."""
    params = {
        k: v for k, v in {"limit": limit, "offset": offset}.items() if v is not None
    }
    return await _client(config).get_crawl_logs(job_id, **params)


@tool
async def list_discovered_urls(
    job_id: str,
    limit: int | None = None,
    offset: int | None = None,
    config: RunnableConfig = None,
) -> dict:
    """List URLs discovered so far by a crawl job, before they're scraped.
    limit (max 200, default 50) and offset paginate."""
    params = {
        k: v for k, v in {"limit": limit, "offset": offset}.items() if v is not None
    }
    return await _client(config).list_discovered_urls(job_id, **params)


@tool
async def scrape_discovered_urls(
    job_id: str,
    max_pages: int | None = None,
    concurrency: int | None = None,
    scraping_strategy: str | None = None,
    enable_human_behaviors: bool | None = None,
    config: RunnableConfig = None,
) -> dict:
    """Scrape all currently discovered URLs for a crawl job (there's no way to
    pick a subset — it always runs against everything discovered so far).
    Same settings knobs as create_crawl; omit for defaults."""
    payload = {
        "settings": _crawl_settings(
            max_pages,
            concurrency,
            scraping_strategy,
            None,
            None,
            enable_human_behaviors,
        )
    }
    return await _client(config).scrape_discovered_urls(job_id, payload)


@tool
async def get_dashboard_overview(config: RunnableConfig = None) -> dict:
    """Get a summary overview of crawl activity (counts, recent jobs, etc)."""
    return await _client(config).get_dashboard_overview()


@tool
async def list_data(
    job_id: str | None = None,
    format: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    config: RunnableConfig = None,
) -> dict:
    """List scraped data items. job_id filters to one crawl, q is a free-text
    search, format filters by content format, limit (max 200, default 50) and
    offset paginate."""
    params = {
        k: v
        for k, v in {
            "job_id": job_id,
            "format": format,
            "q": q,
            "limit": limit,
            "offset": offset,
        }.items()
        if v is not None
    }
    return await _client(config).list_data(**params)


@tool
async def get_data_item(result_id: str, config: RunnableConfig = None) -> dict:
    """Get a single scraped data item by its result id."""
    return await _client(config).get_data_item(result_id)


@tool
async def export_data(
    job_id: str | None = None,
    ids: list[str] | None = None,
    q: str | None = None,
    format: str | None = None,
    archive_format: str = "zip",
    config: RunnableConfig = None,
) -> dict:
    """Kick off a bulk export of scraped data. job_id/ids/q select which items
    to export — omit all three to export everything. ids is a specific list
    of result ids (max 500). format converts content (e.g. "markdown").
    archive_format is "zip" (default) or "ndjson". Returns an export
    identifier — report that to the user rather than fetching raw file bytes.
    """
    payload: dict = {"archive_format": archive_format}
    if job_id is not None:
        payload["job_id"] = job_id
    if ids is not None:
        payload["ids"] = ids
    if q is not None:
        payload["q"] = q
    if format is not None:
        payload["format"] = format
    return await _client(config).export_data(payload)


@tool
async def list_crawl_templates(config: RunnableConfig = None) -> dict:
    """List available crawl configuration templates."""
    return await _client(config).list_crawl_templates()


@tool
async def get_crawl_template(template_id: str, config: RunnableConfig = None) -> dict:
    """Get the settings of a specific crawl template."""
    return await _client(config).get_crawl_template(template_id)


@tool
async def web_search(
    query: str, max_results: int = 10, config: RunnableConfig = None
) -> dict:
    """Search the public web for pages matching a query — use this to find
    candidate URLs before crawling, e.g. turn "covid 19 bangla data" into a
    handful of real news/data site URLs, then pass the ones worth crawling to
    create_crawl. This only finds URLs, it doesn't fetch or crawl page
    content. Returns {"results": [{"title", "url", "snippet"}, ...]}, most
    relevant first. max_results caps how many come back (default 10, max 20).
    """
    api_key = config["configurable"].get("search_api_key")
    if not api_key:
        raise RuntimeError(
            "Web search isn't configured — save a search API key via "
            'PUT /api/settings/agent with {"search": {...}} before using '
            "this tool."
        )
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": min(max_results, 20),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post("https://api.tavily.com/search", json=payload)
        response.raise_for_status()
        data = response.json()
    return {
        "results": [
            {
                "title": result.get("title"),
                "url": result.get("url"),
                "snippet": result.get("content"),
            }
            for result in data.get("results", [])
        ]
    }


TOOLS = [
    create_crawl,
    list_crawls,
    get_crawl,
    cancel_crawl,
    retry_crawl,
    delete_crawl,
    get_crawl_logs,
    list_discovered_urls,
    scrape_discovered_urls,
    get_dashboard_overview,
    list_data,
    get_data_item,
    export_data,
    list_crawl_templates,
    get_crawl_template,
    web_search,
]
