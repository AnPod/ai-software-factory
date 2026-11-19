"""Payment provider adapter. Reads the API key from the environment, never from code."""

import os


def provider_key() -> str:
    key = os.environ.get("TINYSHOP_PAYMENTS_KEY")
    if not key:
        raise RuntimeError("TINYSHOP_PAYMENTS_KEY is not set")
    return key
