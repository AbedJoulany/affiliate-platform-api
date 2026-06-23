import re

TELEGRAM_NUMERIC_CHANNEL_ID = re.compile(r"^-100\d{8,15}$")
TELEGRAM_USERNAME = re.compile(r"^@[a-zA-Z][a-zA-Z0-9_]{4,31}$")


def normalize_telegram_channel_id(value: str) -> str:
    channel_id = value.strip()
    if not channel_id:
        raise ValueError("Telegram channel ID cannot be empty")

    if channel_id.startswith("-100") and channel_id[1:].isdigit():
        if not TELEGRAM_NUMERIC_CHANNEL_ID.match(channel_id):
            raise ValueError(
                "Invalid numeric Telegram channel ID. Expected format: -100XXXXXXXXXX"
            )
        return channel_id

    if not channel_id.startswith("@"):
        channel_id = f"@{channel_id}"

    if not TELEGRAM_USERNAME.match(channel_id):
        raise ValueError(
            "Invalid Telegram channel username. Use @channel_username or -100XXXXXXXXXX"
        )

    return channel_id


def is_valid_telegram_channel_id(value: str) -> bool:
    try:
        normalize_telegram_channel_id(value)
        return True
    except ValueError:
        return False
