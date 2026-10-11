"""Adapter registry: add/remove sources independently."""
from .github import GithubAdapter
from .github_ar import GithubArabicAdapter
from .hackernews import HackerNewsAdapter
from .mostaql import MostaqlAdapter
from .reddit import RedditAdapter
from .rss import RssAdapter
from .stackexchange import StackExchangeAdapter
from .stubs import (DiscordAdapter, FacebookAdapter, FreelanceAdapter,
                    InstagramAdapter, TelegramAdapter, TikTokAdapter,
                    XAdapter, YouTubeAdapter)


def all_adapters(cfg):
    live = [HackerNewsAdapter(cfg), GithubAdapter(cfg), StackExchangeAdapter(cfg),
            RssAdapter(cfg), RedditAdapter(cfg), MostaqlAdapter(cfg),
            GithubArabicAdapter(cfg)]
    stubs = [XAdapter(cfg), FacebookAdapter(cfg), YouTubeAdapter(cfg), TikTokAdapter(cfg),
             InstagramAdapter(cfg), TelegramAdapter(cfg), DiscordAdapter(cfg),
             FreelanceAdapter(cfg)]
    return live, stubs
