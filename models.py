from pydantic import BaseModel, HttpUrl, Field


class Product(BaseModel):
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
