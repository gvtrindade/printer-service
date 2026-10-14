from pydantic import BaseModel, HttpUrl, Field


class Product(BaseModel):
    # Identifier assigned by the caller (the web app). Echoed back in the
    # print-result webhook so the caller can mark the product as printed.
    id: str = Field(min_length=1)
    title: str
    price: float | None = None


class PrintRequest(BaseModel):
    job_id: str = Field(min_length=1)
    callback_url: HttpUrl
    template: str = Field(min_length=1, description="Base64-encoded SVG template")
    products: list[Product] = Field(min_length=1)


class PrintResponse(BaseModel):
    job_id: str
    queued: int
