import hashlib
from datetime import datetime, timezone

MEMORY_KINDS = {"decision", "learning", "context", "todo"}

# Boost suave: empate de relevância vai para a memória mais nova,
# sem deixar recência soterrar relevância.
RECENCY_BOOST = 0.25


def memory_id(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def age_days(created_at_iso: str, now: datetime | None = None) -> float:
    created = datetime.fromisoformat(created_at_iso)
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - created).total_seconds() / 86400.0)


def recency_factor(created_at_iso: str, now: datetime | None = None) -> float:
    return 1.0 + RECENCY_BOOST / (1.0 + age_days(created_at_iso, now))
