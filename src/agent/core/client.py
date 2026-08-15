from __future__ import annotations

import httpx

from src.core.config import settings


class OneCrawlerClient:
    """Thin async wrapper the agent's tools use to drive the OneCrawler REST API on the
    user's behalf."""

    def __init__(self, token: str, base_url: str | None = None) -> None:
        self._token = token
        self._base_url = base_url or settings.AGENT_API_BASE_URL

    async def request(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

    async def create_crawl(self, payload: dict) -> dict:
        return await self.request("POST", "/crawls", json=payload)

    async def list_crawls(self, **params) -> dict:
        return await self.request("GET", "/crawls", params=params)

    async def get_crawl(self, job_id: str) -> dict:
        return await self.request("GET", f"/crawls/{job_id}")

    async def delete_crawl(self, job_id: str) -> dict:
        return await self.request("DELETE", f"/crawls/{job_id}")

    async def cancel_crawl(self, job_id: str) -> dict:
        return await self.request("POST", f"/crawls/{job_id}/cancel")

    async def retry_crawl(self, job_id: str) -> dict:
        return await self.request("POST", f"/crawls/{job_id}/retry")

    async def get_crawl_logs(self, job_id: str, **params) -> dict:
        return await self.request("GET", f"/crawls/{job_id}/logs", params=params)

    async def list_discovered_urls(self, job_id: str, **params) -> dict:
        return await self.request("GET", f"/crawls/{job_id}/discovered", params=params)

    async def scrape_discovered_urls(self, job_id: str, payload: dict) -> dict:
        return await self.request("POST", f"/crawls/{job_id}/scrape", json=payload)

    async def get_dashboard_overview(self) -> dict:
        return await self.request("GET", "/dashboard/overview")

    async def list_data(self, **params) -> dict:
        return await self.request("GET", "/data", params=params)

    async def get_data_item(self, result_id: str) -> dict:
        return await self.request("GET", f"/data/{result_id}")

    async def export_data(self, payload: dict) -> dict:
        return await self.request("POST", "/data/export", json=payload)

    async def list_crawl_templates(self) -> dict:
        return await self.request("GET", "/settings/templates")

    async def get_crawl_template(self, template_id: str) -> dict:
        return await self.request("GET", f"/settings/templates/{template_id}")
