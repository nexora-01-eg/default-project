"""Stub adapters for sources NOT safely/reliably collectable in MVP.

Each exposes the adapter interface with status 'not_implemented' + honest reason,
so the dashboard shows coverage truthfully instead of faking support.
"""
from .base import SourceAdapter


class _Stub(SourceAdapter):
    reason = "not implemented in MVP"
    support_status = "NOT_SUPPORTED"  # NOT_SUPPORTED | CONFIG_REQUIRED | BLOCKED | RATE_LIMITED
    interval_s = 86400
    languages = []
    source_type = "stub"

    def collect(self):
        return []

    def safe_collect(self, db_path):
        from .. import db as DB
        DB.mark_source(db_path, self.name, True)
        return []


class XAdapter(_Stub):
    name = "x"
    kind = "stub"
    support_status = "NOT_SUPPORTED"
    reason = "requires paid API / auth; no scraping (ToS). Planned Phase 3."


class FacebookAdapter(_Stub):
    name = "facebook"
    kind = "stub"
    support_status = "NOT_SUPPORTED"
    reason = "login-walled + anti-bot; no bypass allowed. Planned Phase 2 via public pages RSS only."


class YouTubeAdapter(_Stub):
    name = "youtube"
    kind = "stub"
    support_status = "CONFIG_REQUIRED"
    reason = "needs Data API key (config youtube_api_key) — none configured; comment scraping unreliable."


class TikTokAdapter(_Stub):
    name = "tiktok"
    kind = "stub"
    support_status = "NOT_SUPPORTED"
    reason = "no public API; scraping violates ToS. Deferred."


class InstagramAdapter(_Stub):
    name = "instagram"
    kind = "stub"
    support_status = "NOT_SUPPORTED"
    reason = "login-walled; no bypass allowed. Deferred."


class TelegramAdapter(_Stub):
    name = "telegram"
    kind = "stub"
    support_status = "CONFIG_REQUIRED"
    source_type = "chat"
    reason = ("needs public-channel opt-in (config telegram_channels) AND a lawful fetch method; "
              "no channels configured and no scraper will be built around access controls.")


class DiscordAdapter(_Stub):
    name = "discord"
    kind = "stub"
    support_status = "CONFIG_REQUIRED"
    source_type = "chat"
    reason = "needs bot token + guild opt-in. Deferred."


class FreelanceAdapter(_Stub):
    name = "freelance_marketplaces"
    kind = "stub"
    support_status = "CONFIG_REQUIRED"
    source_type = "marketplace"
    reason = ("most marketplaces are auth/CAPTCHA-walled; public RSS where available comes via "
              "RssAdapter. Configure marketplace_feeds to enable.")
