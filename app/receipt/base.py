from typing import Protocol

from pydantic import BaseModel


class ReceiptLineItem(BaseModel):
    description: str
    amount: float  # display units (e.g. 12.50 for $12.50)
    quantity: int | None = None


class ReceiptExtractionResult(BaseModel):
    title: str | None = None  # best-guess description (e.g. "Ciao restaurant dinner")
    line_items: list[ReceiptLineItem]
    extras: float | None = None  # sum of tax, tips, fees, service charges — everything except line items


class ReceiptExtractor(Protocol):
    async def extract(self, image_bytes: bytes, content_type: str) -> ReceiptExtractionResult: ...
