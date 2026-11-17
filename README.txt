# HABARI AI Studio — local prototype

This is a small local web interface and Python bridge. It does **not** contain the speech model.
It sends text to a separate self-hosted KokoroTTS server running on the same PC.

## What this first prototype does
- Accepts a short script (up to 12,000 characters).
- Offers American male Kokoro voice IDs.
- Requests MP3 audio from the local Kokoro server.
- Downloads the generated MP3.
- Splits longer test scripts into smaller requests. Multiple MP3 parts require FFmpeg to join.

The 60-minute project workflow, persistent job queue, Cloudflare integration, and HABARI website integration are intentionally not included yet.

## Start the HABARI interface
1. Install Python 3.11 or newer (if it is not already installed).
2. Extract this folder somewhere easy to find, e.g. `Documents\HABARI-AI-Studio`.
3. Open Command Prompt in this folder.
4. Run:

   `py start_habari.py`

5. Open `http://127.0.0.1:8787` in your browser.

## Speech engine prerequisite
The interface expects a self-hosted KokoroTTS server at:

`http://127.0.0.1:7860`

The current KokoroTTS project documents a local UI and an OpenAI-compatible MP3 endpoint:
https://github.com/hangry-labs/kokoroTTS

Start that local engine separately before clicking Generate MP3. If it is not running, the interface will show a connection error.

Optional environment variables:
- `KOKORO_URL` — change the local engine URL.
- `KOKOROTTS_API_KEY` — bearer key if you enable API-key protection in KokoroTTS.

## Important
- This app binds only to `127.0.0.1`, so it is accessible only from your own computer.
- Do not expose this prototype directly to the public internet.
- The code does not send scripts to HABARI, Cloudflare, or an external TTS API.
- Check the licenses of the model, voices, and dependencies before commercial distribution.
