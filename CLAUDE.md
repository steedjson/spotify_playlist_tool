# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A single-purpose Python CLI tool that reads Chinese song lists from `songs.csv`, searches Spotify for each track using the Web API, and bulk-adds matched songs to a playlist. Uses `spotipy` library with Authorization Code Flow.

## Structure

```
main.py          # All logic in one file: auth, search, playlist add
config.py        # Loads .env file, validates SPOTIPY_CLIENT_ID/SECRET
songs.csv        # Input data (UTF-8 BOM), columns: song, artist
.env             # Credentials (gitignored)
.env.example     # Template for .env
.spotify_tokens.json  # Cached OAuth tokens (gitignored)
```

## Commands

```bash
# Install dependency
pip install spotipy

# First-time OAuth authorization (opens browser)
python main.py auth

# Run: search songs.csv and add to playlist
python main.py

# Force re-authorization
python main.py --force-auth
```

## Key Details

- **Playlist ID** is hardcoded in `main.py:PLAYLIST_ID` — change it to target a different playlist, or pass as `sys.argv[1]` (currently the tool ignores positional args and uses the constant).
- **Search strategy**: exact match (`song + artist`) → fallback to song-only with artist fuzzy-check in top 5 results → retry up to 3 times with 2s delay → 0.5s rate limit between requests.
- **Auth flow**: local HTTP server on `http://127.0.0.1:8080/callback` receives the OAuth code. Token cached to `.spotify_tokens.json`.
- **Duplicate prevention**: checks existing playlist tracks before adding.
- **CSV format**: `song,artist` header, UTF-8 BOM encoded. Empty rows and rows missing either field are skipped.
- **No test suite** — this is a throwaway automation script. Manual verification via CLI is sufficient.
- **No build/lint step** — pure Python script, no packaging.

## Configuration

Credentials come from `.env` (auto-loaded by `config.py`) or environment variables:
- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`
- `PLAYLIST_ID` — target playlist ID; fallback to CLI arg or hardcoded default `3iTS9MK0wnrUFqpKb5NBLo`

Scopes: `playlist-modify-public playlist-modify-private`
