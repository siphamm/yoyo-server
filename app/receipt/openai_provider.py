import base64

from agents import Agent, Runner

from app.receipt.base import ReceiptExtractionResult

INSTRUCTIONS = """\
You are a receipt parser. Given a receipt image, extract a title, individual line items, and extras.

Rules:
- title: a short, descriptive name for this receipt (e.g. "Ciao restaurant dinner", "Uber ride to airport", "7-Eleven snacks"). Infer from the merchant name and items.
- line_items: only actual purchased items/products/services with their prices
- amount is the total price for that line item (price * quantity), as a decimal number with full precision
- quantity is optional (null if not visible)
- extras: the sum of ALL non-item charges — tax, tips, service charges, fees, gratuity, etc. Add them all together into one number. null if none found.
- Do NOT include tax/tips/fees/service charges as line_items
- Do NOT detect or return currency — just extract the raw numbers
- Keep descriptions concise but recognizable
- If the receipt is not in English, translate title and descriptions to English"""

agent = Agent(
    name="Receipt Scanner",
    instructions=INSTRUCTIONS,
    model="gpt-4o",
    output_type=ReceiptExtractionResult,
)


class OpenAIReceiptExtractor:
    """Receipt extraction using OpenAI Agents SDK with GPT-4o vision."""

    async def extract(self, image_bytes: bytes, content_type: str) -> ReceiptExtractionResult:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        media_type = content_type or "image/jpeg"

        result = await Runner.run(
            agent,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract line items and total from this receipt."},
                        {"type": "input_image", "image_url": f"data:{media_type};base64,{b64_image}"},
                    ],
                }
            ],
        )

        return result.final_output
