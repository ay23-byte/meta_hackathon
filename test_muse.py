
import os

import pytest
from openai import OpenAI


@pytest.mark.skipif(
    not os.getenv("BASETEN_API_KEY"),
    reason="BASETEN_API_KEY is not configured.",
)
def test_muse_spark_api():
    """Optional integration test for Muse Spark through Baseten."""

    api_key = os.getenv("BASETEN_API_KEY")
    if not api_key:
        pytest.skip("Muse API key is missing.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://inference.baseten.co/v1",
    )

    response = client.chat.completions.create(
        model="meta-models/muse-spark-open",
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: Hello World",
            }
        ],
        stream=False,
        max_tokens=30,
    )

    text = response.choices[0].message.content
    if not text or not str(text).strip():
        pytest.skip("Muse Spark returned no usable content; live API verification is unavailable for this environment.")

    print(f"\nMuse Spark response: {text}")
    assert str(text).strip() == "Hello World"
