import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from models import Book
from worker import PrintJob, PrintResult, _process_job, _build_webhook_payload, worker


def _make_job(**overrides):
    defaults = dict(
        job_id="test-job",
        callback_url="http://example.com/hook",
        template="<svg><text>{{title}}</text></svg>",
        books=[Book(id="b1", title="Dune", author="Herbert", price="10")],
    )
    defaults.update(overrides)
    return PrintJob(**defaults)


@pytest.mark.asyncio
async def test_process_job_success():
    job = _make_job()
    with patch("worker.render_label", return_value=b"ZPL"), \
         patch("worker.send_to_printer"):
        result = await _process_job(job)
    assert result.printed_ids == ["b1"]
    assert result.errors == []


@pytest.mark.asyncio
async def test_process_job_continues_on_error():
    job = _make_job(books=[
        Book(id="b1", title="Dune", author="H", price="10"),
        Book(id="b2", title="Foundation", author="A", price="12"),
    ])
    call_count = 0

    def fake_send(zpl):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from printer import PrinterError
            raise PrinterError("fail")

    with patch("worker.render_label", return_value=b"ZPL"), \
         patch("worker.send_to_printer", side_effect=fake_send):
        result = await _process_job(job)
    assert result.printed_ids == ["b2"]
    assert len(result.errors) == 1
    assert result.errors[0]["id"] == "b1"


def test_build_webhook_payload_ok():
    job = _make_job()
    result = PrintResult(printed_ids=["b1", "b2"])
    payload = _build_webhook_payload(job, result)
    assert payload == {"job_id": "test-job", "status": "ok", "ids": ["b1", "b2"]}


def test_build_webhook_payload_error():
    job = _make_job()
    result = PrintResult(
        printed_ids=["b1"],
        errors=[{"id": "b2", "error": "fail"}],
    )
    payload = _build_webhook_payload(job, result)
    assert payload == {
        "job_id": "test-job",
        "status": "error",
        "ids": ["b1"],
        "errors": [{"id": "b2", "error": "fail"}],
    }


@pytest.mark.asyncio
async def test_worker_processes_jobs_and_calls_webhook():
    queue: asyncio.Queue[PrintJob] = asyncio.Queue()
    job = _make_job()
    await queue.put(job)

    with patch("worker.render_label", return_value=b"ZPL"), \
         patch("worker.send_to_printer"), \
         patch("worker.send_webhook", new_callable=AsyncMock) as mock_webhook:
        task = asyncio.create_task(worker(queue))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    mock_webhook.assert_awaited_once()
    args = mock_webhook.call_args
    assert args[0][0] == "http://example.com/hook"
    assert args[0][1]["status"] == "ok"
    assert args[0][1]["ids"] == ["b1"]