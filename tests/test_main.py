import base64
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


def _b64(svg: str) -> str:
    return base64.b64encode(svg.encode()).decode()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_print_endpoint_returns_202():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "job_id": "job-123",
            "callback_url": "http://example.com/hook",
            "template": _b64("<svg><text>{{title}}</text></svg>"),
            "books": [{"title": "Dune", "price": "10"}],
        }
        with patch("main.app.state") as mock_state:
            mock_queue = AsyncMock()
            mock_state.queue = mock_queue
            resp = await client.post("/print", json=payload)

    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"] == "job-123"
    assert body["queued"] == 1
    mock_queue.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_print_endpoint_rejects_unknown_placeholders():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "job_id": "job-456",
            "callback_url": "http://example.com/hook",
            "template": _b64("<svg><text>{{unknown}}</text></svg>"),
            "books": [{"title": "Dune", "price": "10"}],
        }
        resp = await client.post("/print", json=payload)

    assert resp.status_code == 422
    assert "unknown placeholders" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_print_endpoint_rejects_empty_books():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "job_id": "job-789",
            "callback_url": "http://example.com/hook",
            "template": _b64("<svg><text>{{title}}</text></svg>"),
            "books": [],
        }
        resp = await client.post("/print", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_print_endpoint_rejects_invalid_base64():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "job_id": "job-abc",
            "callback_url": "http://example.com/hook",
            "template": "not-valid-base64!!!",
            "books": [{"title": "Dune", "price": "10"}],
        }
        resp = await client.post("/print", json=payload)

    assert resp.status_code == 422
    assert "base64" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_health_endpoint():
    from unittest.mock import MagicMock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_queue = MagicMock()
        mock_queue.qsize.return_value = 0
        app.state.queue = mock_queue
        with patch("main.printer_is_available", return_value=True):
            resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["printer_available"] is True
    assert body["queue_size"] == 0
