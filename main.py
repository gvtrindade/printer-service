import asyncio
import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from models import PrintRequest, PrintResponse
from printer import printer_is_available
from templating import validate_template
from worker import PrintJob, worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue: asyncio.Queue[PrintJob] = asyncio.Queue()
    task = asyncio.create_task(worker(queue))
    app.state.queue = queue
    app.state.worker_task = task
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Label Printer Service", lifespan=lifespan)


@app.post("/print", response_model=PrintResponse, status_code=202)
async def print_labels(req: PrintRequest):
    try:
        svg_template = base64.b64decode(req.template, validate=True).decode()
    except Exception:
        raise HTTPException(status_code=422, detail="template is not valid base64")

    unknown = validate_template(svg_template)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown placeholders in template: {unknown}",
        )

    job = PrintJob(
        job_id=req.job_id,
        callback_url=str(req.callback_url),
        template=svg_template,
        books=req.books,
    )
    await app.state.queue.put(job)
    return PrintResponse(job_id=req.job_id, queued=len(req.books))


@app.get("/health")
async def health():
    return {
        "printer_available": printer_is_available(),
        "queue_size": app.state.queue.qsize(),
    }
