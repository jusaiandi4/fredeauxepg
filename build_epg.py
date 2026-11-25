#!/usr/bin/env python3
"""
Build a USA EPG (XMLTV) matched to your IPTV playlist's channel names.

What it does
  1. Pulls your Xtream playlist (get.php) and keeps every "USA*" channel.
  2. Pulls three free US EPG sources from epgshare01:
       - epg_ripper_US2.xml.gz        (national networks)
       - epg_ripper_US_SPORTS1.xml.gz (regional sports/team feeds)
       - epg_ripper_US_LOCALS1.xml.gz (ABC/CBS/NBC/FOX/... local affiliates)
  3. Matches your channels to those guides by normalized name (nationals)
     and by station callsign (locals).
  4. Emits a single XMLTV file whose <display-name> EQUALS your exact
     tvg-name, so every player (TiviMate, Smarters, ...) auto-matches
     even though your playlist ships with empty tvg-id.

Usage
  python3 build_epg.py --m3u /path/to/playlist.m3u --out tvsat_usa_epg.xml.gz
  python3 build_epg.py --m3u-url "http://host:port/get.php?...&type=m3u_plus&output=ts"
  (EPG sources are auto-downloaded and cached under ./cache unless --use-cache only)

Secrets never belong in source control: pass the m3u-url at runtime, not in code.
"""
import argparse, gzip, hashlib, html, os, re, sys, urllib.request

EPG_BASE = "https://epgshare01.online/epgshare01/"
SOURCES = [
    ("epg_ripper_US2.xml.gz", "national"),
    ("epg_ripper_US_SPORTS1.xml.gz", "sports"),
    ("epg_ripper_US_LOCALS1.xml.gz", "locals"),
]

# channels whose group or name marks them as live-event placeholders (no EPG exists)
EVENT_GROUPS = ("nba", "mlb", "nfl", "nhl", "ncaaf", "mls", "ufc", "ppv", "events")
EVENT_MARKERS = ("no scheduled event", "no event", "scheduled event")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# --------------------------------------------------------------------------
# name normalization
# --------------------------------------------------------------------------
QUALITY = re.compile(r"\b(4k|fhd|uhd|hd|sd|raw|hevc|h\.?264|h\.?265)\b", re.I)
PUNCT = re.compile(r"[^\w\s]")
COMPASS = re.compile(r"\b(east|west|north|south|pacific|atlantic|central|mountain|feed|national feed)\b", re.I)

def norm(s: str) -> str:
    """Exact-match key: strip tags, quality, compass directions, leading 'the'."""
    s = s.lower()
    s = re.sub(r"^(usa?|us)\b[\s:;|\-]+", "", s)          # leading country tag
    s = re.sub(r"\b(the)\b", " ", s)
    s = s.replace("&", " and ")
    s = s.replace("'", "").replace("\u2019", "")          # America's -> americas
    s = PUNCT.sub(" ", s)
    s = QUALITY.sub(" ", s)
    s = COMPASS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

GENERIC = {"channel", "network", "tv", "the", "us", "usa", "hd", "fhd", "uhd", "4k",
           "plus", "live", "stream", "feed", "east", "west", "north", "south",
           "pacific", "atlantic", "central", "mountain"}

def core_tokens(s: str) -> set:
    return {t for t in norm(s).split() if t not in GENERIC}

def norm_id(ident: str) -> str:
    ident = re.sub(r"\.(us2|us_locals1|us)$", "", ident, flags=re.I)
    return norm(ident.replace(".", " "))

def slug(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]

# curated overrides for names the guides rename, rebrand, or number differently
ALIASES = {
    # sports
    "espn": "ESPN.HD.us2", "espn 1": "ESPN.HD.us2", "espn hd": "ESPN.HD.us2",
    "espn 2": "ESPN2.HD.us2", "espn2": "ESPN2.HD.us2",
    "espn news": "ESPNEWS.HD.us2", "espn news us": "ESPNEWS.HD.us2", "espnews": "ESPNEWS.HD.us2",
    "espn u": "ESPNU.HD.us2", "espu": "ESPNU.HD.us2",
    "espn deportes": "ESPN.Deportes.HD.us2",
    "fox sports 1": "FS1.Fox.Sports.1.HD.us2", "fs1": "FS1.Fox.Sports.1.HD.us2",
    "fox sports 2": "FS2.Fox.Sports.2.HD.us2", "fs2": "FS2.Fox.Sports.2.HD.us2",
    "fox soccer plus": "Fox.Soccer.Plus.HD.us2",
    "golf channel": "Golf.Channel.HD.us2", "nbc golf": "Golf.Channel.HD.us2",
    "cbs sports network": "CBS.Sports.Network.HD.us2",
    "acc network": "ACC.Network.us2",
    "sec network": "SEC.Network.HD.us2", "sec network espn": "SEC.Network.HD.us2",
    "nfl network": "NFL.Network.HD.us2", "nfl network 1": "NFL.Network.HD.us2",
    "nfl redzone": "NFL.RedZone.HD.us2",
    "nba tv": "NBA.TV.HD.us2",
    "mlb network": "MLB.Network.HD.us2",
    "motortrend": "MOTORTREND.HD.us2", "velocity": "MOTORTREND.HD.us2",
    "discovery velocity": "MOTORTREND.HD.us2",
    # rebrands
    "diy network": "Magnolia.Network.HD.us2",
    "viceland": "Vice.HD.us2",
    "great american country": "Great.American.Family.HD.us2",
    "discovery science": "Science.Channel.HD.us2",
    "epix": "MGM+.HD.us2", "epix 2": "MGM+.Hits.HD.us2",
    "epix hits": "MGM+.Marquee.HD.us2", "epix drive in": "MGM+.Drive-In.us2",
    "tcm": "Turner.Classic.Movies.HD.us2", "turner classic movies": "Turner.Classic.Movies.HD.us2",
    # movie / premium
    "hbo 2": "HBO2.HD.us2",
    "hallmark movies and mysteries": "Hallmark.Mystery.HD.us2",
    "hallmark movies & mysteries": "Hallmark.Mystery.HD.us2",
    "hallmark movies & my steries": "Hallmark.Mystery.HD.us2",
    "hallmark mystery": "Hallmark.Mystery.HD.us2",
    "lifetime movie network": "Lifetime.Real.Women.us2",
    "lifetime movies": "Lifetime.HD.us2",
    "the movie channel xtra": "The.Movie.Channel.Extra.HD.us2",
    "movie channel xtra": "The.Movie.Channel.Extra.HD.us2",
    "sundance": "SundanceTV.HD.us2", "sundance tv": "SundanceTV.HD.us2",
    "sony movies": "Sony.Movie.Channel.HD.us2",
    "fxm": "FX.Movie.Channel.HD.us2", "fx movie channel": "FX.Movie.Channel.HD.us2",
    "indie plex": "IndiePlex.HD.us2", "indieplex": "IndiePlex.HD.us2",
    "reelz": "ReelzChannel.HD.us2", "reelzchannel": "ReelzChannel.HD.us2",
    "usa network": "USA.Network.HD.us2",
    "tru tv": "truTV.HD.us2", "trutv": "truTV.HD.us2",
    # news / general
    "news nation": "NewsNation.us2", "newsnation": "NewsNation.us2",
    "newsmax": "Newsmax.TV.HD.us2", "newsmax tv": "Newsmax.TV.HD.us2",
    "newsmax backup": "Newsmax.TV.HD.us2",
    "cnbc tv en": "CNBC.HD.us2", "cnbc world": "CNBC.World.us2",
    "bbc world news": "BBC.News.(North.America).HD.us2",
    "bbc world": "BBC.News.(North.America).HD.us2",
    "c span 1": "CSPAN.us2", "c span 2": "CSPAN2.us2", "c span 3": "CSPAN3.us2",
    "cspan": "CSPAN.us2", "cspan2": "CSPAN2.us2", "cspan3": "CSPAN3.us2",
    "nasa tv": "NASA.Plus.us2", "nasa": "NASA.Plus.us2",
    "outdoor channel": "Outdoor.Channel.HD.us2",
    "awe channel": "AWE.Plus.us2", "awe": "AWE.Plus.us2",
    "american heroes channel": "American.Heroes.Channel.HD.us2",
    "one america news": "One.America.News.Network.HD.us2", "oann": "One.America.News.Network.HD.us2",
    "fuse": "Fuse.HD.us2",
    "axs tv": "AXS.TV.us2", "axs": "AXS.TV.us2",
    # music / kids
    "mtv 2": "MTV2:.Music.Television.HD.us2", "mtv2": "MTV2:.Music.Television.HD.us2",
    "starz kids and family": "Starz.Kids.HD.us2", "starz kids": "Starz.Kids.HD.us2",
}

# --------------------------------------------------------------------------
# m3u parsing
# --------------------------------------------------------------------------
CALLSIGN = re.compile(r"\b([KW][A-Z]{2,3})(?:\-[DTVLC]+\d*)?\b")

def parse_m3u(path: str):
    """Return list of dicts for USA live channels: {name, id, group, callsign}."""
    rows, name, tid, group = [], None, None, None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#EXTINF"):
                m = re.search(r'tvg-name="([^"]*)"', line)
                name = m.group(1) if m else None
                m = re.search(r'tvg-id="([^"]*)"', line)
                tid = m.group(1) if m else ""
                m = re.search(r'group-title="([^"]*)"', line)
                group = m.group(1) if m else ""
            elif line and not line.startswith("#") and name is not None:
                if group.lower().startswith("usa"):
                    cs = None
                    m = CALLSIGN.search(name or "")
                    if m:
                        cs = m.group(1)
                    rows.append({"name": name, "id": tid, "group": group, "callsign": cs})
                name, tid, group = None, None, None
    return rows

def is_event_ch(row: dict) -> bool:
    g = row["group"].lower()
    n = row["name"].lower()
    if any(e in g for e in EVENT_GROUPS):
        return True
    if any(m in n for m in EVENT_MARKERS):
        return True
    return False

# --------------------------------------------------------------------------
# fetch helpers
# --------------------------------------------------------------------------
def fetch(url: str, dest: str):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())

# --------------------------------------------------------------------------
# guide index building (id -> normalized key / callsign)
# --------------------------------------------------------------------------
def build_index(path: str, kind: str):
    """Return (by_norm, by_callsign, by_core) mapping keys -> real channel id."""
    by_norm, by_callsign, by_core = {}, {}, {}
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.search(r'<channel id="([^"]+)"', line)
            if m:
                cid = m.group(1)
                if kind == "locals":
                    base = re.sub(r"\.(us_locals1|us2|us)$", "", cid, flags=re.I)
                    base = re.sub(r"-(DT|TV|LD|CD|D)\d*$", "", base, flags=re.I)
                    by_callsign.setdefault(base.upper(), cid)
                else:
                    key = norm_id(cid)
                    by_norm.setdefault(key, cid)
                    cs = frozenset(core_tokens(key))
                    if cs:
                        # keep the shortest / most-specific id for a given core set
                        prev = by_core.get(cs)
                        if prev is None or len(norm_id(cid)) < len(norm_id(prev)):
                            by_core[cs] = cid
    return by_norm, by_callsign, by_core

# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------
def match_channel(row: dict, nat, sports, nat_core, sports_core, locals_by_cs, valid_ids):
    """Return (source_kind, source_channel_id) or (None, None)."""
    # 1) locals by callsign (highest precision)
    if row["callsign"] and row["callsign"] in locals_by_cs:
        return "locals", locals_by_cs[row["callsign"]]
    key = norm(row["name"])
    # 2) exact normalized name
    for table, kind in ((sports, "sports"), (nat, "national")):
        if key in table:
            return kind, table[key]
    # 3) curated alias (validated against real source ids)
    if key in ALIASES and ALIASES[key] in valid_ids:
        return "national", ALIASES[key]
    # 4) core-token fuzzy (his tokens must all appear in the source)
    his = core_tokens(row["name"])
    if his:
        best = None
        for core_map, kind in ((sports_core, "sports"), (nat_core, "national")):
            for cs, cid in core_map.items():
                if his <= cs:                       # his core is subset of source
                    if best is None or len(cs) < best[0]:
                        best = (len(cs), kind, cid)
        if best:
            return best[1], best[2]
    return None, None

# --------------------------------------------------------------------------
# emission
# --------------------------------------------------------------------------
def esc(s: str) -> str:
    return html.escape(s, quote=False)

def emit(out, mapping, by_source_files):
    """mapping: his_name -> {id, sid, src}; write <channel> + matched <programme>."""
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n')
    out.write('<tv generator-info-name="tvsat-usa-epg">\n')
    for name, info in mapping.items():
        out.write(f'  <channel id="{info["id"]}">\n')
        out.write(f'    <display-name>{esc(name)}</display-name>\n')
        out.write("  </channel>\n")
    # stream each source and copy matched programme blocks (multi-line aware)
    wanted_by_src = {}   # src_kind -> {source_channel_id -> our_id}
    for name, info in mapping.items():
        wanted_by_src.setdefault(info["src"], {})[info["sid"]] = info["id"]
    for src_kind, sidmap in wanted_by_src.items():
        path = by_source_files[src_kind]
        opener = gzip.open if path.endswith(".gz") else open
        copying = False
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if copying:
                    out.write(line)
                    if "</programme>" in line:
                        copying = False
                    continue
                m = re.search(r'<programme [^>]*channel="([^"]+)"', line)
                if m and m.group(1) in sidmap:
                    new_id = sidmap[m.group(1)]
                    out.write(line.replace(f'channel="{m.group(1)}"', f'channel="{new_id}"', 1))
                    if "</programme>" not in line:
                        copying = True
    out.write("</tv>\n")

# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m3u", help="local playlist path")
    ap.add_argument("--m3u-url", help="playlist URL (get.php)")
    ap.add_argument("--out", default="tvsat_usa_epg.xml.gz")
    ap.add_argument("--cache-dir", default="cache")
    ap.add_argument("--use-cache", action="store_true", help="skip network fetches")
    args = ap.parse_args()

    os.makedirs(args.cache_dir, exist_ok=True)

    if args.m3u_url:
        args.m3u = os.path.join(args.cache_dir, "playlist.m3u")
        if not args.use_cache or not os.path.exists(args.m3u):
            fetch(args.m3u_url, args.m3u)
    if not args.m3u or not os.path.exists(args.m3u):
        sys.exit("need --m3u or --m3u-url")

    rows = [r for r in parse_m3u(args.m3u) if not is_event_ch(r)]
    print(f"USA channels (non-event): {len(rows)}")

    # fetch + index sources
    by_source_files = {}
    nat = sports = {}
    nat_core = sports_core = {}
    locals_by_cs = {}
    for fname, kind in SOURCES:
        path = os.path.join(args.cache_dir, fname)
        if not args.use_cache or not os.path.exists(path):
            fetch(EPG_BASE + fname, path)
        by_source_files[kind] = path
        bn, bc, bcore = build_index(path, kind)
        if kind == "national":
            nat, nat_core = bn, bcore
        elif kind == "sports":
            sports, sports_core = bn, bcore
        else:
            locals_by_cs = bc

    mapping = {}
    unmatched = []
    valid_ids = set(nat.values()) | set(sports.values())
    for r in rows:
        kind, sid = match_channel(r, nat, sports, nat_core, sports_core, locals_by_cs, valid_ids)
        if sid:
            oid = f"tvsat-{slug(r['name'])}"
            mapping[r["name"]] = {"id": oid, "sid": sid, "src": kind}
        else:
            unmatched.append(r)

    matched_names = set(mapping)
    matched_rows = [r for r in rows if r["name"] in matched_names]

    # write output
    outdir = os.path.dirname(args.out)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    if args.out.endswith(".gz"):
        out = gzip.open(args.out, "wt", encoding="utf-8")
    else:
        out = open(args.out, "w", encoding="utf-8")
    emit(out, mapping, by_source_files)
    out.close()

    n_total = len(rows)
    n_match = len(mapping)
    print(f"matched: {n_match}/{n_total} ({100*n_match/max(1,n_total):.1f}%)")
    print(f"unmatched: {len(unmatched)}")
    with open("unmatched.txt", "w") as f:
        for r in sorted(unmatched, key=lambda x: (x["group"], x["name"])):
            f.write(f"{r['group']}\t{r['name']}\tcs={r['callsign'] or ''}\n")
    print("unmatched written to unmatched.txt")
    print(f"output: {args.out}")

if __name__ == "__main__":
    main()
