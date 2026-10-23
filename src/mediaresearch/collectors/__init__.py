from mediaresearch.collectors.base import Collector, RawDocument
from mediaresearch.collectors.google_news import GoogleNewsCollector
from mediaresearch.collectors.rss import RssCollector
from mediaresearch.collectors.telegram import TelegramCollector
from mediaresearch.collectors.vk import VkCollector


def build_collectors(sources: dict) -> dict[str, Collector]:
    """Включённые в config/sources.yaml сборщики по имени."""
    collectors: dict[str, Collector] = {}
    if sources.get("google_news", {}).get("enabled"):
        collectors["google_news"] = GoogleNewsCollector()
    if feeds := sources.get("rss"):
        collectors["rss"] = RssCollector(feeds)
    if channels := sources.get("telegram"):
        collectors["telegram"] = TelegramCollector(channels)
    vk = sources.get("vk", {})
    if vk.get("enabled"):
        collectors["vk"] = VkCollector(vk.get("communities", []))
    return collectors


__all__ = ["Collector", "RawDocument", "build_collectors"]
