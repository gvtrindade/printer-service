import asyncio
import logging
from dataclasses import dataclass, field

from book_service import create_book
from models import Book
from printer import render_label, send_to_printer, PrinterError
from qr import make_qr_data_uri
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
    printed_ids: list[int] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


async def _print_one(job: PrintJob, book: Book) -> int:
    book_id = await create_book()
    data = book.model_dump()
    data["id"] = book_id
    data["qr"] = make_qr_data_uri(f"E:{book_id}")
    svg_text = populate(job.template, data)
    zpl = await asyncio.to_thread(render_label, svg_text)
    await asyncio.to_thread(send_to_printer, zpl)
    return book_id


async def _process_job(job: PrintJob) -> PrintResult:
    result = PrintResult()
    for book in job.books:
        try:
            printed_id = await _print_one(job, book)
            result.printed_ids.append(printed_id)
        except PrinterError as e:
            logger.error("job %s book %r failed: %s", job.job_id, book.title, e)
            result.errors.append({"title": book.title, "error": str(e)})
        except Exception as e:
            logger.exception("job %s book %r unexpected error", job.job_id, book.title)
            result.errors.append({"title": book.title, "error": str(e)})
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
