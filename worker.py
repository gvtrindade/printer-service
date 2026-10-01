import asyncio
import logging
from dataclasses import dataclass, field

from models import Book
from printer import render_label, send_to_printer, PrinterError
from templating import populate
from webhook import send_webhook

logger = logging.getLogger(__name__)


@dataclass
class PrintJob:
    job_id: str
    callback_url: str
    template: str
    books: list[Book]


@dataclass
class PrintResult:
    printed_ids: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


async def _print_one(job: PrintJob, book: Book) -> str | None:
    svg_text = populate(job.template, book.model_dump())
    zpl = await asyncio.to_thread(render_label, svg_text)
    await asyncio.to_thread(send_to_printer, zpl)
    return book.id


async def _process_job(job: PrintJob) -> PrintResult:
    result = PrintResult()
    for book in job.books:
        try:
            printed_id = await _print_one(job, book)
            result.printed_ids.append(printed_id)
        except PrinterError as e:
            logger.error("job %s book %s failed: %s", job.job_id, book.id, e)
            result.errors.append({"id": book.id, "error": str(e)})
        except Exception as e:
            logger.exception("job %s book %s unexpected error", job.job_id, book.id)
            result.errors.append({"id": book.id, "error": str(e)})
    return result


def _build_webhook_payload(job: PrintJob, result: PrintResult) -> dict:
    if result.errors:
        return {
            "job_id": job.job_id,
            "status": "error",
            "ids": result.printed_ids,
            "errors": result.errors,
        }
    return {
        "job_id": job.job_id,
        "status": "ok",
        "ids": result.printed_ids,
    }


async def worker(queue: asyncio.Queue[PrintJob]) -> None:
    while True:
        job = await queue.get()
        try:
            result = await _process_job(job)
            payload = _build_webhook_payload(job, result)
            await send_webhook(job.callback_url, payload)
        except Exception:
            logger.exception("job %s worker loop error", job.job_id)
        finally:
            queue.task_done()
