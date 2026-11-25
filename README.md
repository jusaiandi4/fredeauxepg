# fredeauxepg — USA EPG (self-hosted, free, auto-refreshing)

Your IPTV panel ships a 60 MB EPG that only covers ~163 USA channels and leaves
`tvg-id=""` on the rest, so players show "No information". This repo fixes it:
it matches **every USA channel in your playlist by name** against free US guide
data and serves one EPG URL you hand to your customers.

## Your EPG URL

```
https://jusaiandi4.github.io/fredeauxepg/tvsat_usa_epg.xml.gz
```

That URL never changes. Hand it to every customer.

## How customers load it

- **TiviMate** (recommended): Settings → EPG → Add source → paste the URL.
  Then per playlist: assign the EPG source. Channels match by name automatically.
- **IPTV Smarters / Smarters Pro**: Settings → EPG → add the URL.
- **Any Xtream app**: paste the URL in the "EPG" field next to the playlist URL.

## How it stays fresh

A GitHub Action (`.github/workflows/epg.yml`) runs daily and rebuilds the guide
from your playlist (fetched via the `M3U_URL` secret, so your username/password
never live in the repo) plus three free US EPG sources from epgshare01.

`build_epg.py` does the matching: national networks by name, local
ABC/CBS/NBC/FOX affiliates by station callsign. Output is
`tvsat_usa_epg.xml.gz`; unmatched channels are listed in `unmatched.txt`.

## Coverage notes

- Event channels (NBA/MLB/NFL/NHL/NCAAF/MLS/UFC "No Scheduled Event" placeholders)
  are skipped on purpose — no schedule exists for them anywhere.
- A few networks have no free US guide (HGTV, OWN, Bally/FanDuel RSNs, BEIN
  sub-feeds, Canadian TSN/Sportsnet). Those are the only real gaps.
