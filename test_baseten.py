
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env", override=True)

api_key = os.getenv("BASETEN_API_KEY", "").strip()

if not api_key or api_key == "your_baseten_api_key_here":
    raise RuntimeError(
        "Set your actual Baseten API key in .env first."
    )

client = OpenAI(
    base_url="https://inference.baseten.co/v1",
    api_key=api_key,
    timeout=60.0,
)

try:
    response = client.chat.completions.create(
        model="meta-models/muse-spark-open",
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: Muse Spark connection successful",
            }
        ],
        max_tokens=256,
    )
    print(response.choices[0].message.content)

except Exception as exc:
    # Print the status and safe error text, never the API key.
    print("Error type:", type(exc).__name__)
    print("HTTP status:", getattr(exc, "status_code", "unknown"))
    print("Error details:", getattr(exc, "message", str(exc)))
