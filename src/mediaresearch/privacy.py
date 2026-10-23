import hashlib
import hmac

from mediaresearch.config import settings


def hash_author(source_type: str, author_id: str | int, salt: str | None = None) -> str:
    """Псевдоним автора: по нему можно считать уникальных авторов, но не узнать ID."""
    key = (salt or settings.author_hash_salt).encode()
    msg = f"{source_type}:{author_id}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
