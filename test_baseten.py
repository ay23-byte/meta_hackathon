
from openai import OpenAI

import ask_muse
import provider_config


def main():
    api_key = provider_config.get_api_key()

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
        print("Provider error:", ask_muse.describe_provider_error(exc) if ask_muse._http_status(exc) is not None else str(ask_muse._network_error(exc)))


if __name__ == "__main__":
    main()
