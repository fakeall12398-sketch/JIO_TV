import os
import requests
import gzip
import re
from datetime import datetime
import xml.etree.ElementTree as ET
import time
from concurrent.futures import ThreadPoolExecutor, as_completed



M3U_FILE = os.getenv("M3U_FILE", "jstar.m3u")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "jio_epg.xml.gz")

BASE_URL = "https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
    "Accept": "application/json",
    "Referer": "https://www.jiotv.com/",
    "Origin": "https://www.jiotv.com",
}

SHOW_IMAGE_BASE = "https://jiotvimages.cdn.jio.com/dare_images/shows/"
TIMEOUT = 20
MAX_WORKERS = 10   # 🔥 Increase = faster (8–15 safe range)


# ======================
# CLEAN M3U PARSER
# ======================
def parse_m3u(path):
    channels = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()

        if line.startswith("#EXTINF"):
            tvg_id_match = re.search(r'tvg-id="([^"]+)"', line)
            tvg_logo_match = re.search(r'tvg-logo="([^"]+)"', line)

            if not tvg_id_match:
                continue

            tvg_id = tvg_id_match.group(1).strip()
            tvg_logo = tvg_logo_match.group(1).strip() if tvg_logo_match else ""

            # Only text after first comma = channel name
            if "," in line:
                name = line.split(",", 1)[1].strip()
            else:
                name = "Unknown"

            channels.append({
                "id": tvg_id,
                "name": name,
                "logo": tvg_logo
            })

    print(f"✅ Loaded {len(channels)} channels from M3U")
    return channels


# ======================
# FETCH EPG FROM JIO
# ======================
def fetch_epg(channel_id, offset):
    params = {
        "channel_id": channel_id,
        "offset": offset
    }

    try:
        r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=TIMEOUT)

        if r.status_code == 404:
            return channel_id, offset, None

        if r.status_code != 200:
            print(f"❌ {channel_id} offset={offset} -> {r.status_code}")
            return channel_id, offset, None

        return channel_id, offset, r.json()

    except Exception as e:
        print(f"❌ {channel_id} offset={offset} -> {e}")
        return channel_id, offset, None


# ======================
# MAIN
# ======================
start_time = time.time()

channels = parse_m3u(M3U_FILE)

tv = ET.Element("tv")

# 1️⃣ CHANNEL SECTION
for ch in channels:
    ch_el = ET.SubElement(tv, "channel", {"id": ch["id"]})
    ET.SubElement(ch_el, "display-name").text = ch["name"]

    if ch["logo"]:
        ET.SubElement(ch_el, "icon", {"src": ch["logo"]})


# 2️⃣ PARALLEL FETCH
tasks = []
results = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    for offset in range(-1, 4):  # yesterday → +3 days
        for ch in channels:
            tasks.append(executor.submit(fetch_epg, ch["id"], offset))

    for future in as_completed(tasks):
        cid, offset, data = future.result()
        if not data or "epg" not in data:
            continue

        results.append((cid, data))


# 3️⃣ BUILD PROGRAMMES (🔥 FINAL TIME FIX)
print(f"\n📺 Building programmes...")

for cid, data in results:
    for p in data["epg"]:
        try:
            # 🔥 FINAL FIX: Jio timestamps are already IST → DO NOT CONVERT
            start = datetime.fromtimestamp(p["startEpoch"] / 1000)
            end   = datetime.fromtimestamp(p["endEpoch"] / 1000)

        except Exception:
            continue

        prog = ET.SubElement(tv, "programme", {
            "start": start.strftime("%Y%m%d%H%M%S +0530"),
            "stop":  end.strftime("%Y%m%d%H%M%S +0530"),
            "channel": cid
        })

        ET.SubElement(prog, "title").text = str(p.get("showname", "Unknown")).strip()
        ET.SubElement(prog, "desc").text = str(p.get("description", "")).strip()

        if "genre" in p:
            ET.SubElement(prog, "category").text = str(p["genre"]).strip()

        # 🔥 Program poster image
        poster = p.get("episodePoster")
        if poster:
            ET.SubElement(prog, "icon", {
                "src": SHOW_IMAGE_BASE + poster
            })


# 4️⃣ SAVE XMLTV (GZIP)
xml_data = ET.tostring(tv, encoding="utf-8")

with gzip.open(OUTPUT_FILE, "wb") as f:
    f.write(xml_data)

elapsed = time.time() - start_time

print("\n🎉 DONE (FAST + TIME FIXED)")
print("📦 Output:", OUTPUT_FILE)
print("📏 Size:", len(xml_data), "bytes")
print(f"⏱ Time taken: {elapsed:.2f} seconds")
print(f"🚀 Threads used: {MAX_WORKERS}")
