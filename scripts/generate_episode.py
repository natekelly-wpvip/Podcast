#!/usr/bin/env python3
"""
Generate a podcast episode: script via Claude, audio via ElevenLabs.
Outputs episode_meta.json for downstream steps.
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


def generate_script(episode_number: int) -> tuple[str, str]:
    """Use Claude to write the episode title and script."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%B %d, %Y")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        messages=[
            {
                "role": "user",
                "content": f"""You are the host of "{PODCAST_NAME}," episode {episode_number} — a weekly AI-generated podcast at the intersection of media and artificial intelligence.

Today is {today}. Write a full ~10-minute podcast episode (approximately 1,300-1,500 words of spoken content).

Requirements:
- Strong opening hook — do not start with "welcome back" or generic intros
- Cover 2-3 substantive themes in media and AI: newsroom automation, AI-generated content ethics, publisher monetization, platform algorithm shifts, notable product launches, audience behavior research, or similar
- Sharp analysis and a clear point of view, not just summaries
- Conversational but authoritative tone — sounds natural when read aloud
- No stage directions, no brackets like [INTRO] or [MUSIC], no section headers
- No filler transitions like "moving on" or "so there you have it"
- End with a specific, forward-looking observation or question — not a generic sign-off

Also provide a compelling episode title (5-10 words, no colons).

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
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", output_path],
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

    print(f"[1/3] Generating script for episode {episode_number}...")
    title, script = generate_script(episode_number)
    print(f"  Title: {title}")
    print(f"  Script length: {len(script):,} characters")

    # Save script for reference
    script_path = Path(f"episodes/ep{episode_number:03d}_script.txt")
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(f"Episode {episode_number}: {title}\n\n{script}")

    print(f"[2/3] Generating audio...")
    audio_path = f"episodes/ep{episode_number:03d}.mp3"
    file_size = generate_audio(script, audio_path)
    print(f"  Saved: {audio_path} ({file_size / 1_000_000:.1f} MB)")

    print(f"[3/3] Writing episode metadata...")
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
