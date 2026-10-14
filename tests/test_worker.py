import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from models import Product
from worker import PrintJob, PrintResult, _process_job, _build_webhook_payload, worker


def _make_job(**overrides):
    defaults = dict(
        job_id="test-job",
        callback_url="http://example.com/hook",
        template="<svg><text>{{title}}</text></svg>",
        products=[Product(title="Dune", price="10")],
    )
    defaults.update(overrides)
    return PrintJob(**defaults)


@pytest.mark.asyncio
async def test_process_job_success():
    job = _make_job()
    with patch("worker.create_product", new_callable=AsyncMock, return_value=123), \
         patch("worker.render_label", return_value=b"ZPL"), \
         patch("worker.send_to_printer"):
        result = await _process_job(job)
    assert result.printed_ids == [123]
    assert result.errors == []


@pytest.mark.asyncio
async def test_process_job_continues_on_error():
    job = _make_job(products=[
        Product(title="Dune", price="10"),
        Product(title="Foundation", price="12"),
    ])
    call_count = 0

    def fake_send(zpl):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from printer import PrinterError
            raise PrinterError("fail")

    create_product = AsyncMock(side_effect=[11, 22])
    with patch("worker.create_product", create_product), \
         patch("worker.render_label", return_value=b"ZPL"), \
         patch("worker.send_to_printer", side_effect=fake_send):
        result = await _process_job(job)
    assert result.printed_ids == [22]
    assert len(result.errors) == 1
    assert result.errors[0]["title"] == "Dune"


@pytest.mark.asyncio
async def test_print_one_embeds_qr_from_new_id():
    job = _make_job()
    product = Product(title="Dune", price="10")
    captured = {}

    def fake_populate(template, data):
        captured.update(data)
        return "<svg/>"

    with patch("worker.create_product", new_callable=AsyncMock, return_value=123), \
         patch("worker.make_qr_data_uri", return_value="data:image/png;base64,QR") as make_qr, \
         patch("worker.populate", side_effect=fake_populate), \
         patch("worker.render_label", return_value=b"ZPL"), \
         patch("worker.send_to_printer"):
        from worker import _print_one

        printed_id = await _print_one(job, product)

    assert printed_id == 123
    make_qr.assert_called_once_with("E:123")
    assert captured["id"] == 123
    assert captured["qr"] == "data:image/png;base64,QR"
    assert captured["title"] == "Dune"


def test_build_webhook_payload_ok():
    job = _make_job()
    result = PrintResult(printed_ids=[11, 22])
    payload = _build_webhook_payload(job, result)
    assert payload == {"job_id": "test-job", "status": "ok", "ids": [11, 22]}


def test_build_webhook_payload_error():
    job = _make_job()
    result = PrintResult(
        printed_ids=[11],
        errors=[{"title": "Foundation", "error": "fail"}],
    )
    payload = _build_webhook_payload(job, result)
    assert payload == {
        "job_id": "test-job",
        "status": "error",
        "ids": [11],
        "errors": [{"title": "Foundation", "error": "fail"}],
    }


@pytest.mark.asyncio
async def test_worker_processes_jobs_and_calls_webhook():
    queue: asyncio.Queue[PrintJob] = asyncio.Queue()
    job = _make_job()
    await queue.put(job)

    with patch("worker.create_product", new_callable=AsyncMock, return_value=123), \
         patch("worker.render_label", return_value=b"ZPL"), \
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
    assert args[0][1]["ids"] == [123]
