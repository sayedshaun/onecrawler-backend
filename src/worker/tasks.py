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


def now_ms() -> int:
    return int(time.time() * 1000)


def decode_url(url: str) -> str:
    """Decode a percent-encoded URL so it's human-readable in the UI."""
    return unquote(url, errors="replace")


def summarize_content(
    content: Any, fallback_url: str
) -> tuple[str, str, int, str, dict]:
    """Returns (url, title, word_count, preview, payload) for a scraped content item.

    `payload` is always a dict so heuristic and genai extractions (which produce
    different shapes) can share the same JSONB column.
    """
    if isinstance(content, dict):
        url = decode_url(content.get("url") or fallback_url)
        title = content.get("title") or url
        text = content.get("text") or content.get("raw_text") or ""
        if not text:
            text = json.dumps(content, ensure_ascii=False, default=str)
        payload = content
    else:
        url = decode_url(fallback_url)
        title = url
        text = str(content)
        payload = {"text": text}

    word_count = len(text.split()) if text else 0
    preview = text[:400]
    return url, title, word_count, preview, payload


async def log(db, job_id: str, level: str, message: str) -> None:
    db.add(LogLine(job_id=job_id, timestamp=now_ms(), level=level, message=message))
    await db.commit()


async def is_cancelled(db, job_id: str) -> bool:
    status = await db.scalar(select(CrawlJob.status).where(CrawlJob.id == job_id))
    return status == CrawlStatus.CANCELLED


async def run_crawl_job(ctx, job_id: str) -> None:
    async with async_session() as db:
        job = await db.get(CrawlJob, job_id)
        if job is None or job.status == CrawlStatus.CANCELLED:
            return

        job.status = CrawlStatus.RUNNING
        job.started_at = now_ms()
        await db.commit()
        await log(db, job_id, "info", f"Starting {job.mode} job for {job.target_url}")

        try:
            settings = await build_settings(db, job.settings, job.user_id)
        except Exception as exc:
            job.status = CrawlStatus.FAILED
            job.error = f"Invalid settings: {exc}"
            job.finished_at = now_ms()
            await db.commit()
            await log(db, job_id, "error", job.error)
            return

        try:
            if job.mode == CrawlMode.SITEMAP:
                cancelled = await run_sitemap(db, job, settings)
            elif job.mode == CrawlMode.LINK_EXTRACTION:
                cancelled = await run_link_extraction(db, job, settings)
            elif job.mode == CrawlMode.CRAWLER:
                filters = build_filter_chain(job.filters)
                cancelled = await run_crawler(db, job, settings, filters)
            elif job.mode == CrawlMode.SCRAPER:
                cancelled = await run_scraper(db, job, settings)
            else:
                raise ValueError(f"Unknown crawl mode: {job.mode}")

            job.status = CrawlStatus.CANCELLED if cancelled else CrawlStatus.COMPLETED
            job.finished_at = now_ms()
            await db.commit()
            await log(db, job_id, "info", f"Job {job.status}")

        except Exception as exc:
            job.status = CrawlStatus.FAILED
            job.error = str(exc)
            job.finished_at = now_ms()
            await db.commit()
            await log(db, job_id, "error", f"Job failed: {exc}")


async def run_sitemap(db, job: CrawlJob, settings) -> bool:
    engine = SiteMap(settings)
    urls = await engine.run(job.target_url)

    for url in urls:
        if await is_cancelled(db, job.id):
            await log(db, job.id, "warn", "Cancelled before completion")
            return True

        db.add(
            DiscoveredUrl(
                job_id=job.id,
                url=decode_url(url),
                discovered_at=now_ms(),
                status="extracted",
            )
        )
        job.urls_discovered += 1
        await db.commit()

    return False


async def run_link_extraction(db, job: CrawlJob, settings) -> bool:
    async with LinkExtractor(settings) as engine:
        if settings.link_extraction_strategy == "shallow":
            urls = await engine.run(job.target_url)
            for url in urls:
                if await is_cancelled(db, job.id):
                    await log(db, job.id, "warn", "Cancelled before completion")
                    return True
                db.add(
                    DiscoveredUrl(
                        job_id=job.id,
                        url=decode_url(url),
                        discovered_at=now_ms(),
                        status="extracted",
                    )
                )
                job.urls_discovered += 1
            await db.commit()
            return False

        async for url in engine.stream(job.target_url):
            if await is_cancelled(db, job.id):
                await log(db, job.id, "warn", "Cancelled before completion")
                return True
            db.add(
                DiscoveredUrl(
                    job_id=job.id,
                    url=decode_url(url),
                    discovered_at=now_ms(),
                    status="extracted",
                )
            )
            job.urls_discovered += 1
            await db.commit()

    return False


async def run_crawler(db, job: CrawlJob, settings, filters) -> bool:
    async with Crawler(settings) as engine:
        async for content in engine.stream(job.target_url, filters=filters):
            if await is_cancelled(db, job.id):
                await log(db, job.id, "warn", "Cancelled before completion")
                return True

            url, title, word_count, preview, payload = summarize_content(
                content, job.target_url
            )

            db.add(
                DiscoveredUrl(
                    job_id=job.id, url=url, discovered_at=now_ms(), status="extracted"
                )
            )
            db.add(
                CrawlResultItem(
                    job_id=job.id,
                    url=url,
                    title=title,
                    word_count=word_count,
                    format=settings.scraping_output_format,
                    extracted_at=now_ms(),
                    preview=preview,
                    content=payload,
                )
            )
            job.urls_discovered += 1
            job.urls_scraped += 1
            await db.commit()

    return False


async def run_scraper(db, job: CrawlJob, settings) -> bool:
    # A job created straight from POST /crawls has no seed_urls — create_crawl only
    # records target_url, and scraping that URL is the whole point of this mode.
    # seed_urls is set only by scrape-from-discovered and by retry.
    urls = job.seed_urls or [job.target_url]
    async with Scraper(settings) as engine:
        async for item in engine.stream(urls):
            if await is_cancelled(db, job.id):
                await log(db, job.id, "warn", "Cancelled before completion")
                return True

            url, title, word_count, preview, payload = summarize_content(
                item.get("result"), item.get("url", job.target_url)
            )

            db.add(
                DiscoveredUrl(
                    job_id=job.id, url=url, discovered_at=now_ms(), status="extracted"
                )
            )
            db.add(
                CrawlResultItem(
                    job_id=job.id,
                    url=url,
                    title=title,
                    word_count=word_count,
                    format=settings.scraping_output_format,
                    extracted_at=now_ms(),
                    preview=preview,
                    content=payload,
                )
            )
            job.urls_discovered += 1
            job.urls_scraped += 1
            await db.commit()

    if job.urls_scraped == 0:
        await log(db, job.id, "warn", f"Scraped nothing from {len(urls)} URL(s)")
    return False
