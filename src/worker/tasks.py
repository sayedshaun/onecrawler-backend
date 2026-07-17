import json
import time
from typing import Any
from urllib.parse import unquote

from onecrawler import Crawler, LinkExtractor, Scraper, SiteMap
from sqlalchemy import select

from src.db.models import (
    CrawlJob,
    CrawlMode,
    CrawlResultItem,
    CrawlStatus,
    DiscoveredUrl,
    LogLine,
)
from src.db.pg import async_session
from src.worker.settings_builder import build_filter_chain, build_settings


def _now_ms() -> int:
    return int(time.time() * 1000)


def _decode_url(url: str) -> str:
    """Decode a percent-encoded URL so it's human-readable in the UI."""
    return unquote(url, errors="replace")


def _summarize_content(
    content: Any, fallback_url: str
) -> tuple[str, str, int, str, dict]:
    """Returns (url, title, word_count, preview, payload) for a scraped content item.

    `payload` is always a dict so heuristic and genai extractions (which produce
    different shapes) can share the same JSONB column.
    """
    if isinstance(content, dict):
        url = _decode_url(content.get("url") or fallback_url)
        title = content.get("title") or url
        text = content.get("text") or content.get("raw_text") or ""
        if not text:
            text = json.dumps(content, ensure_ascii=False, default=str)
        payload = content
    else:
        url = _decode_url(fallback_url)
        title = url
        text = str(content)
        payload = {"text": text}

    word_count = len(text.split()) if text else 0
    preview = text[:400]
    return url, title, word_count, preview, payload


async def _log(db, job_id: str, level: str, message: str) -> None:
    db.add(LogLine(job_id=job_id, timestamp=_now_ms(), level=level, message=message))
    await db.commit()


async def _is_cancelled(db, job_id: str) -> bool:
    status = await db.scalar(select(CrawlJob.status).where(CrawlJob.id == job_id))
    return status == CrawlStatus.CANCELLED


async def run_crawl_job(ctx, job_id: str) -> None:
    async with async_session() as db:
        job = await db.get(CrawlJob, job_id)
        if job is None or job.status == CrawlStatus.CANCELLED:
            return

        job.status = CrawlStatus.RUNNING
        job.started_at = _now_ms()
        await db.commit()
        await _log(db, job_id, "info", f"Starting {job.mode} job for {job.target_url}")

        try:
            settings = await build_settings(db, job.settings, job.user_id)
        except Exception as exc:
            job.status = CrawlStatus.FAILED
            job.error = f"Invalid settings: {exc}"
            job.finished_at = _now_ms()
            await db.commit()
            await _log(db, job_id, "error", job.error)
            return

        try:
            if job.mode == CrawlMode.SITEMAP:
                cancelled = await _run_sitemap(db, job, settings)
            elif job.mode == CrawlMode.LINK_EXTRACTION:
                cancelled = await _run_link_extraction(db, job, settings)
            elif job.mode == CrawlMode.CRAWLER:
                filters = build_filter_chain(job.filters)
                cancelled = await _run_crawler(db, job, settings, filters)
            elif job.mode == CrawlMode.SCRAPER:
                cancelled = await _run_scraper(db, job, settings)
            else:
                raise ValueError(f"Unknown crawl mode: {job.mode}")

            job.status = CrawlStatus.CANCELLED if cancelled else CrawlStatus.COMPLETED
            job.finished_at = _now_ms()
            await db.commit()
            await _log(db, job_id, "info", f"Job {job.status}")

        except Exception as exc:
            job.status = CrawlStatus.FAILED
            job.error = str(exc)
            job.finished_at = _now_ms()
            await db.commit()
            await _log(db, job_id, "error", f"Job failed: {exc}")


async def _run_sitemap(db, job: CrawlJob, settings) -> bool:
    engine = SiteMap(settings)
    urls = await engine.run(job.target_url)

    for url in urls:
        if await _is_cancelled(db, job.id):
            await _log(db, job.id, "warn", "Cancelled before completion")
            return True

        db.add(
            DiscoveredUrl(
                job_id=job.id,
                url=_decode_url(url),
                discovered_at=_now_ms(),
                status="extracted",
            )
        )
        job.urls_discovered += 1
        await db.commit()

    return False


async def _run_link_extraction(db, job: CrawlJob, settings) -> bool:
    async with LinkExtractor(settings) as engine:
        if settings.link_extraction_strategy == "shallow":
            urls = await engine.run(job.target_url)
            for url in urls:
                if await _is_cancelled(db, job.id):
                    await _log(db, job.id, "warn", "Cancelled before completion")
                    return True
                db.add(
                    DiscoveredUrl(
                        job_id=job.id,
                        url=_decode_url(url),
                        discovered_at=_now_ms(),
                        status="extracted",
                    )
                )
                job.urls_discovered += 1
            await db.commit()
            return False

        async for url in engine.stream(job.target_url):
            if await _is_cancelled(db, job.id):
                await _log(db, job.id, "warn", "Cancelled before completion")
                return True
            db.add(
                DiscoveredUrl(
                    job_id=job.id,
                    url=_decode_url(url),
                    discovered_at=_now_ms(),
                    status="extracted",
                )
            )
            job.urls_discovered += 1
            await db.commit()

    return False


async def _run_crawler(db, job: CrawlJob, settings, filters) -> bool:
    async with Crawler(settings) as engine:
        async for content in engine.stream(job.target_url, filters=filters):
            if await _is_cancelled(db, job.id):
                await _log(db, job.id, "warn", "Cancelled before completion")
                return True

            url, title, word_count, preview, payload = _summarize_content(
                content, job.target_url
            )

            db.add(
                DiscoveredUrl(
                    job_id=job.id, url=url, discovered_at=_now_ms(), status="extracted"
                )
            )
            db.add(
                CrawlResultItem(
                    job_id=job.id,
                    url=url,
                    title=title,
                    word_count=word_count,
                    format=settings.scraping_output_format,
                    extracted_at=_now_ms(),
                    preview=preview,
                    content=payload,
                )
            )
            job.urls_discovered += 1
            job.urls_scraped += 1
            await db.commit()

    return False


async def _run_scraper(db, job: CrawlJob, settings) -> bool:
    urls = job.seed_urls or []
    async with Scraper(settings) as engine:
        async for item in engine.stream(urls):
            if await _is_cancelled(db, job.id):
                await _log(db, job.id, "warn", "Cancelled before completion")
                return True

            url, title, word_count, preview, payload = _summarize_content(
                item.get("result"), item.get("url", job.target_url)
            )

            db.add(
                DiscoveredUrl(
                    job_id=job.id, url=url, discovered_at=_now_ms(), status="extracted"
                )
            )
            db.add(
                CrawlResultItem(
                    job_id=job.id,
                    url=url,
                    title=title,
                    word_count=word_count,
                    format=settings.scraping_output_format,
                    extracted_at=_now_ms(),
                    preview=preview,
                    content=payload,
                )
            )
            job.urls_discovered += 1
            job.urls_scraped += 1
            await db.commit()

    return False
