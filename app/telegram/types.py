from dataclasses import dataclass


@dataclass
class InlineUrlButton:
    text: str
    url: str


@dataclass
class TelegramPublishResult:
    chat_id: str
    message_id: int
    message_type: str
