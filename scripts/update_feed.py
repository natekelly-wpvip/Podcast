#!/usr/bin/env python3
"""
Update the podcast RSS feed (feed.xml) with a new episode.
Called after audio is uploaded to GitHub Releases.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path

PODCAST_TITLE = "Signal & Noise"
PODCAST_DESCRIPTION = (
    "Weekly AI-generated analysis at the intersection of media and artificial intelligence. "
    "Script written by Claude. Voice by ElevenLabs. Published every Friday."
)
PODCAST_AUTHOR = "Signal & Noise"
PODCAST_LANGUAGE = "en-us"
PODCAST_CATEGORY = "Technology"
PODCAST_EXPLICIT = "no"


def get_podcast_link() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "YOUR_USERNAME/YOUR_REPO")
    owner, name = repo.split("/", 1)
    return f"https://{owner}.github.io/{name}"


def build_initial_feed(podcast_link: str) -> str:
    return f"""<?xml version='1.0' encoding='utf-8'?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{PODCAST_TITLE}</title>
    <description>{PODCAST_DESCRIPTION}</description>
    <link>{podcast_link}</link>
    <language>{PODCAST_LANGUAGE}</language>
    <lastBuildDate>{formatdate(usegmt=True)}</lastBuildDate>
    <atom:link href="{podcast_link}/feed.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>{PODCAST_AUTHOR}</itunes:author>
    <itunes:category text="{PODCAST_CATEGORY}"/>
    <itunes:explicit>{PODCAST_EXPLICIT}</itunes:explicit>
    <itunes:type>episodic</itunes:type>
  </channel>
</rss>"""


def add_episode(feed_content: str, episode: dict, audio_url: str, pub_date: str) -> str:
    """Insert a new <item> block at the top of the channel, after channel metadata."""
    ep_num = episode["number"]
    title = f"Ep. {ep_num}: {episode['title']}"
    description = episode.get("description", "")
    file_size = episode["file_size"]

    item_xml = f"""
    <item>
      <title>{_escape(title)}</title>
      <description>{_escape(description)}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{audio_url}</guid>
      <enclosure url="{audio_url}" type="audio/mpeg" length="{file_size}"/>
      <itunes:episode>{ep_num}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
    </item>"""

    # Update lastBuildDate
    import re
    feed_content = re.sub(
        r"<lastBuildDate>[^<]*</lastBuildDate>",
        f"<lastBuildDate>{pub_date}</lastBuildDate>",
        feed_content,
    )

    # Insert new item right before the first existing <item> or before </channel>
    if "<item>" in feed_content:
        feed_content = feed_content.replace("<item>", item_xml + "\n    <item>", 1)
    else:
        feed_content = feed_content.replace("  </channel>", item_xml + "\n  </channel>")

    return feed_content


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-url", required=True, help="Public URL to the episode MP3")
    args = parser.parse_args()

    with open("episode_meta.json") as f:
        episode = json.load(f)

    podcast_link = get_podcast_link()
    feed_path = Path("feed.xml")
    pub_date = formatdate(usegmt=True)

    if feed_path.exists():
        feed_content = feed_path.read_text()
    else:
        feed_content = build_initial_feed(podcast_link)

    feed_content = add_episode(feed_content, episode, args.audio_url, pub_date)
    feed_path.write_text(feed_content)

    print(f"Feed updated: {feed_path}")
    print(f"  Episode {episode['number']}: {episode['title']}")
    print(f"  Audio URL: {args.audio_url}")
    print(f"  Published: {pub_date}")


if __name__ == "__main__":
    main()
