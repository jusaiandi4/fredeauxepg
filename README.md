tvsat.cc — USA EPG (self-hosted, free, auto-refreshing)
Your IPTV panel ships a 60 MB EPG that only covers ~163 USA channels and leaves tvg-id="" on the rest, so players show "No information". This repo fixes it: it matches every USA channel in your playlist by name against free US guide data and serves one EPG URL you hand to your customers.

What you get
tvsat_usa_epg.xml.gz — one XMLTV guide covering ~880 USA channels (national networks + news + sports + ABC/CBS/NBC/FOX local affiliates), keyed so the <display-name> equals your exact channel name (e.g. US: ESPN 1 HD), so TiviMate / Smarters auto-match with no tvg-id.
Auto-refreshes daily via GitHub Actions (free, no VPS).
One-time setup (≈10 min, free)
Create a GitHub account if you don't have one.
Create a new public repository and push these files to it:
build_epg.py
.github/workflows/epg.yml
.gitignore (optional)
bash


git init && git add -A && git commit -m "epg"
git branch -M main
git remote add origin https://github.com/YOURNAME/YOURREPO.git
git push -u origin main
Add your playlist URL as a secret (keeps your username/password out of the repo):
Repo → Settings → Secrets and variables → Actions → New repository secret
Name: M3U_URL
Value: 
http://tvsat.cc:80/get.php?username=1eb52cd2&password=1ca85ac8&type=m3u_plus&output=ts
Repo → Settings → Pages → Source: GitHub Actions (deploy from Actions).
Repo → Actions → EPG refresh → Run workflow. First run takes ~2 min.
Your EPG URL
After the first successful run:

Code block


https://YOURNAME.github.io/YOURREPO/tvsat_usa_epg.xml.gz
That URL never changes. Hand it to every customer.

How customers load it
TiviMate (recommended): Settings → EPG → Add source → paste the URL. Then per playlist: assign the EPG source. Channels match by name automatically.
IPTV Smarters / Smarters Pro: Settings → EPG → add the URL.
Any Xtream app: paste the URL in the "EPG" field next to the playlist URL.
Rebuild locally
bash


python3 build_epg.py --m3u-url "http://tvsat.cc:80/get.php?username=...&type=m3u_plus&output=ts"
The script auto-downloads the three free EPG sources (epgshare01: US national, US locals, US sports) and caches them under cache/. Output is tvsat_usa_epg.xml.gz; unmatched channels are listed in unmatched.txt.

Coverage notes
Event channels (NBA/MLB/NFL/NHL/NCAAF/MLS/UFC "No Scheduled Event" placeholders) are intentionally skipped — no schedule exists for them anywhere.
A few networks have no free US guide (HGTV, OWN, Bally/FanDuel RSNs, BEIN sub-feeds, Canadian TSN/Sportsnet). Those are the only real gaps.
