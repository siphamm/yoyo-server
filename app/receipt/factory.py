import os

from app.receipt.base import ReceiptExtractor
from app.receipt.openai_provider import OpenAIReceiptExtractor


def get_receipt_extractor() -> ReceiptExtractor:
    """Return the configured receipt extraction provider."""
    provider = os.getenv("RECEIPT_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIReceiptExtractor()
    raise ValueError(f"Unknown receipt provider: {provider}")
