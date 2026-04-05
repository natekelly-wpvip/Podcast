# Signal & Noise

A fully AI-generated podcast about media and artificial intelligence. Script by Claude, voice by ElevenLabs, automated by GitHub Actions. New episodes publish every Friday.

---

## How it works

1. GitHub Actions triggers every Friday at 9 AM ET
2. Claude writes a ~10-minute script on media & AI topics
3. ElevenLabs converts the script to speech (MP3)
4. The audio is uploaded to a GitHub Release
5. `feed.xml` is updated with the new episode and pushed to the repo
6. GitHub Pages serves the RSS feed and landing page

---

## Setup

### 1. Create the GitHub repository

Create a new repo (public recommended for podcast hosting), then push this project to it.

### 2. Enable GitHub Pages

Go to **Settings > Pages** and set the source to `Deploy from a branch`, branch `main`, folder `/ (root)`.

Your podcast will be live at `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME`.

### 3. Add repository secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | (Optional) ElevenLabs voice ID. Defaults to Rachel. |

Get keys at:
- Anthropic: https://console.anthropic.com/
- ElevenLabs: https://elevenlabs.io/

### 4. Update feed.xml

Replace `YOUR_USERNAME` and `YOUR_REPO` in `feed.xml` with your actual GitHub username and repository name.

### 5. Trigger your first episode manually

Go to **Actions > Publish Podcast Episode > Run workflow** to generate your first episode without waiting for Friday.

---

## Submit to podcast directories

Once you have at least one episode, submit your feed URL to podcast directories:

| Directory | Submission URL |
|-----------|---------------|
| Apple Podcasts | https://podcastsconnect.apple.com |
| Spotify | https://podcasters.spotify.com |
| Pocket Casts | https://pocketcasts.com/submit |
| Overcast | Automatic via Apple Podcasts |

Your RSS feed URL: `https://YOUR_USERNAME.github.io/YOUR_REPO/feed.xml`

---

## Customization

### Change the podcast name or description
Edit `PODCAST_TITLE` and `PODCAST_DESCRIPTION` in `scripts/update_feed.py`.

### Change the voice
Set the `ELEVENLABS_VOICE_ID` secret to any voice ID from your ElevenLabs account.
Browse voices at https://elevenlabs.io/voice-library.

### Change the episode prompt
Edit the prompt in `scripts/generate_episode.py` in the `generate_script()` function.

### Change the publish schedule
Edit the cron expression in `.github/workflows/publish.yml`:
```yaml
- cron: "0 13 * * 5"  # Every Friday at 13:00 UTC
```

---

## ElevenLabs plan requirements

A 10-minute episode script is ~9,000 characters. ElevenLabs plans:

| Plan | Characters/month | Enough for |
|------|-----------------|------------|
| Free | 10,000 | ~1 episode |
| Starter ($5/mo) | 30,000 | ~3 episodes |
| Creator ($22/mo) | 100,000 | 10+ episodes |

Recommendation: Creator plan for weekly publishing.

---

## Project structure

```
signal-and-noise/
├── .github/
│   └── workflows/
│       └── publish.yml       # Friday automation
├── scripts/
│   ├── generate_episode.py   # Claude script + ElevenLabs audio
│   └── update_feed.py        # RSS feed updater
├── episodes/                 # Scripts saved here (audio uploaded to Releases)
├── feed.xml                  # RSS feed (auto-updated)
├── index.html                # Podcast landing page
├── requirements.txt
└── .gitignore
```
