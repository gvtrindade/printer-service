import asyncio
import logging
from dataclasses import dataclass, field

from models import Product
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
    products: list[Product]


@dataclass
class PrintResult:
    # Caller-assigned product ids from the print request (see models.Product).
    printed_ids: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


async def _print_one(job: PrintJob, product: Product) -> str:
    # The catalog id reserved upstream (Ziontech/megabazar) identifies the
    # printed copy. Fall back to the caller id when it is missing so labels
    # can still be produced.
    external_id = product.external_id or product.id
    data = product.model_dump(exclude={"id"})
    data["id"] = external_id
    data["e_id"] = external_id
    data["qr"] = make_qr_data_uri(f"E:{external_id}")
    svg_text = populate(job.template, data)
    zpl = await asyncio.to_thread(render_label, svg_text)
    await asyncio.to_thread(send_to_printer, zpl)
    return product.id


async def _process_job(job: PrintJob) -> PrintResult:
    result = PrintResult()
    for product in job.products:
        try:
            printed_id = await _print_one(job, product)
            result.printed_ids.append(printed_id)
        except PrinterError as e:
            logger.error("job %s product %r failed: %s", job.job_id, product.title, e)
            result.errors.append({"title": product.title, "error": str(e)})
        except Exception as e:
            logger.exception("job %s product %r unexpected error", job.job_id, product.title)
            result.errors.append({"title": product.title, "error": str(e)})
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
