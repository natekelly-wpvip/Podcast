#!/usr/bin/env python3
"""
Generate a podcast episode: script via Claude, audio via ElevenLabs.
Outputs episode_meta.json for downstream steps.

News sourcing:
  - Calls Tavily Search API to pull real articles from the past 7 days
  - Claude is grounded in those sources before writing the script
  - No facts are invented — Claude is instructed to flag uncertainty
    and only use what the sources support
"""

import anthropic
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

PODCAST_NAME = "Signal & Noise"
MAX_CHARS_PER_CHUNK = 4500  # ElevenLabs safe limit per request

SEARCH_QUERIES = [
    "AI artificial intelligence media publishing news this week",
    "newsroom AI automation journalism 2025",
    "publisher revenue monetization AI tools news",
    "media industry artificial intelligence announcements",
]


def search_recent_news() -> str:
    """
    Query Tavily for real news from the past 7 days across media and AI topics.
    Returns a formatted string of source material for Claude to work from.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("  Warning: TAVILY_API_KEY not set. Skipping news search.")
        return ""

    all_results = []
    seen_urls = set()

    for query in SEARCH_QUERIES:
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "days": 7,
                    "include_answer": False,
                    "include_raw_content": False,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()

            for result in data.get("results", []):
                url = result.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_results.append({
                    "title": result.get("title", ""),
                    "url": url,
                    "published_date": result.get("published_date", "unknown date"),
                    "content": result.get("content", "").strip(),
                })

        except Exception as e:
            print(f"  Search warning for query '{query}': {e}")
            continue

    if not all_results:
        return ""

    # Format into a readable block for Claude
    lines = [f"SOURCED NEWS — past 7 days ({datetime.now().strftime('%B %d, %Y')})\n"]
    for i, r in enumerate(all_results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    Source: {r['url']}")
        lines.append(f"    Date: {r['published_date']}")
        lines.append(f"    Summary: {r['content'][:400]}")
        lines.append("")

    print(f"  Retrieved {len(all_results)} articles from {len(SEARCH_QUERIES)} queries.")
    return "\n".join(lines)


def generate_script(episode_number: int, source_material: str) -> tuple[str, str]:
    """Use Claude to write the episode title and script, grounded in real sources."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%B %d, %Y")

    sponsor_read = (
        "This episode is brought to you by WordPress VIP and Parse.ly. "
        "WordPress VIP is the enterprise content management platform trusted by the world's leading publishers — "
        "built for scale, security, and editorial speed. "
        "Parse.ly is their real-time analytics suite, giving editorial and audience teams the data they need "
        "to understand what content performs and why. "
        "If you're running a media business, visit wpvip.com to learn more."
    )

    if source_material:
        source_block = f"""You have been given the following real news articles sourced from the past 7 days.
These are your only permitted sources of facts, statistics, company names, product names, and claims.

{source_material}

JOURNALISTIC RULES — follow these strictly:
- Only state facts that are directly supported by the sources above
- If you reference a statistic, company action, product, or event, it must appear in the sources
- If a topic is interesting but the sources are thin on detail, say so honestly ("details are still emerging" or "we're still waiting on more reporting")
- Do not invent quotes, data points, survey results, or named individuals
- Do not blend old knowledge with new sources — if it is not in the sources above, do not state it as current fact
- You may provide analysis and interpretation of the sourced facts — that is your job as a host — but clearly distinguish your take from the reported facts
"""
    else:
        source_block = """No live search results were available this run.
Write a thoughtful, evergreen episode on the state of media and AI — but be explicit with the audience that you are discussing ongoing trends rather than breaking news.
Do not invent specific events, statistics, product launches, or company actions. Speak in general, well-established terms only."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        messages=[
            {
                "role": "user",
                "content": f"""You are Nate Kelly, host of "{PODCAST_NAME}," episode {episode_number} — a weekly AI-generated podcast at the intersection of media and artificial intelligence. Think like an experienced technology journalist: precise, skeptical, well-sourced, and direct.

Today is {today}.

{source_block}

Now write a full ~10-minute episode script (approximately 1,300-1,500 words of spoken content).

Script requirements:
- Open with a strong, specific hook rooted in one of the sourced stories — not a generic observation
- Cover 2-3 stories or themes drawn from the source material above
- Provide sharp editorial analysis — not just summaries. Tell the audience why it matters, what it signals, what to watch for
- Conversational but authoritative tone — reads naturally when spoken aloud
- No stage directions, no brackets like [INTRO] or [MUSIC], no section headers
- No filler phrases like "moving on," "so there you have it," or "it's a fascinating time"
- End with a specific, forward-looking observation or open question — not a generic sign-off

SPONSOR PLACEMENT: After the first story, insert the following sponsor read word-for-word, with one natural transition sentence before it. Do not alter the sponsor copy:

"{sponsor_read}"

Then continue directly into the second story.

Also provide a compelling episode title (5-10 words, no colons) that reflects the actual stories covered.

Respond ONLY in this exact JSON format with no markdown or code fences:
{{"title": "Episode title here", "script": "Full spoken script here..."}}""",
            }
        ],
    )

    raw = response.content[0].text.strip()
    data = json.loads(raw)
    return data["title"], data["script"]


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Split text at sentence boundaries to stay under ElevenLabs per-request limit."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current += (" " if current else "") + sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def tts_chunk(text: str, voice_id: str, api_key: str) -> bytes:
    """Call ElevenLabs TTS for a single text chunk, return audio bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.content


def mix_intro_outro(episode_path: str, output_path: str) -> None:
    """
    Stitch intro + episode + outro using ffmpeg.
    Uses the first 8 seconds of audio/intro.mp3 for both intro and outro.
    Intro: 1s fade in, 2s fade out. Outro: 1s fade in, 3s fade out.
    """
    intro_src = "audio/intro.mp3"
    if not Path(intro_src).exists():
        print("  No audio/intro.mp3 found — skipping intro/outro mix.")
        return

    intro_clip = episode_path + ".intro.mp3"
    outro_clip = episode_path + ".outro.mp3"

    # Trim and fade intro (8 seconds)
    subprocess.run([
        "ffmpeg", "-y", "-i", intro_src, "-t", "8",
        "-af", "afade=t=in:st=0:d=1,afade=t=out:st=6:d=2",
        intro_clip
    ], check=True, capture_output=True)

    # Trim and fade outro (8 seconds, longer fade out)
    subprocess.run([
        "ffmpeg", "-y", "-i", intro_src, "-t", "8",
        "-af", "afade=t=in:st=0:d=1,afade=t=out:st=5:d=3",
        outro_clip
    ], check=True, capture_output=True)

    # Concat using filter_complex — re-encodes all inputs to a consistent
    # format (44.1kHz stereo MP3) before joining, preventing warping caused
    # by sample rate or channel mismatches between intro and speech audio.
    subprocess.run([
        "ffmpeg", "-y",
        "-i", intro_clip,
        "-i", episode_path,
        "-i", outro_clip,
        "-filter_complex",
        "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]",
        "-acodec", "libmp3lame",
        "-ar", "44100",
        "-ac", "2",
        "-q:a", "2",
        output_path
    ], check=True, capture_output=True)

    # Clean up temp files
    for f in [intro_clip, outro_clip]:
        os.remove(f)


def generate_audio(script: str, output_path: str) -> int:
    """Convert script to MP3 via ElevenLabs. Returns file size in bytes."""
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel

    chunks = chunk_text(script)
    print(f"  Splitting into {len(chunks)} chunk(s) for TTS...")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if len(chunks) == 1:
        audio_bytes = tts_chunk(chunks[0], voice_id, api_key)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
    else:
        # Write chunks to temp files, then concat with ffmpeg
        chunk_paths = []
        for i, chunk in enumerate(chunks):
            chunk_path = f"{output_path}.part{i}.mp3"
            print(f"  Generating chunk {i + 1}/{len(chunks)}...")
            audio_bytes = tts_chunk(chunk, voice_id, api_key)
            with open(chunk_path, "wb") as f:
                f.write(audio_bytes)
            chunk_paths.append(chunk_path)

        # Create ffmpeg concat list
        concat_list = output_path + ".txt"
        with open(concat_list, "w") as f:
            for cp in chunk_paths:
                f.write(f"file '{os.path.abspath(cp)}'\n")

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2", "-q:a", "2",
                output_path
            ],
            check=True,
            capture_output=True,
        )

        # Clean up temp files
        for cp in chunk_paths:
            os.remove(cp)
        os.remove(concat_list)

    size = Path(output_path).stat().st_size
    return size


def main():
    episode_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    print(f"[1/4] Searching for news from the past 7 days...")
    source_material = search_recent_news()
    if not source_material:
        print("  No sources retrieved — episode will use evergreen framing.")

    print(f"[2/4] Generating script for episode {episode_number}...")
    title, script = generate_script(episode_number, source_material)
    print(f"  Title: {title}")
    print(f"  Script length: {len(script):,} characters")

    # Save script and sources for reference
    script_path = Path(f"episodes/ep{episode_number:03d}_script.txt")
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(f"Episode {episode_number}: {title}\n\n{script}")

    if source_material:
        sources_path = Path(f"episodes/ep{episode_number:03d}_sources.txt")
        sources_path.write_text(source_material)
        print(f"  Sources saved: {sources_path}")

    print(f"[3/4] Generating audio...")
    raw_audio_path = f"episodes/ep{episode_number:03d}_raw.mp3"
    audio_path = f"episodes/ep{episode_number:03d}.mp3"
    file_size = generate_audio(script, raw_audio_path)
    print(f"  Speech generated: {raw_audio_path} ({file_size / 1_000_000:.1f} MB)")

    print(f"  Mixing intro and outro...")
    mix_intro_outro(raw_audio_path, audio_path)
    os.remove(raw_audio_path)
    file_size = Path(audio_path).stat().st_size
    print(f"  Final episode: {audio_path} ({file_size / 1_000_000:.1f} MB)")

    print(f"[4/4] Writing episode metadata...")
    meta = {
        "number": episode_number,
        "title": title,
        "description": script[:300].rstrip() + "...",
        "script": script,
        "audio_path": audio_path,
        "file_size": file_size,
    }
    with open("episode_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nDone. Episode {episode_number}: {title}")


if __name__ == "__main__":
    main()
