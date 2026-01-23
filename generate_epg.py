import os
import requests
import gzip
import re
from datetime import datetime
import xml.etree.ElementTree as ET
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ======================
# CONFIG (ENV OVERRIDE)
# ======================
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
MAX_WORKERS = 7
MAX_RETRIES = 3
RETRY_DELAY = 3

print_lock = Lock()


# ======================
# CLEAN M3U PARSER
# ======================
def parse_m3u(path):
    channels = []
    if not os.path.exists(path):
        print(f"❌ M3U file not found: {path}")
        return channels

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

            name = line.split(",", 1)[1].strip() if "," in line else "Unknown"

            channels.append({
                "id": tvg_id,
                "name": name,
                "logo": tvg_logo
            })

    print(f"✅ Loaded {len(channels)} channels from M3U")
    return channels


# ======================
# FETCH EPG FROM JIO (WITH RETRY + LOG)
# ======================
def fetch_epg(channel_id, offset, idx, total):
    params = {"channel_id": channel_id, "offset": offset}

    with print_lock:
        print(f"➡️ [{idx}/{total}] Fetching channel={channel_id} offset={offset}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=TIMEOUT)

            if r.status_code == 200:
                with print_lock:
                    print(f"✅ OK  channel={channel_id} offset={offset}")
                return channel_id, offset, r.json()

            if r.status_code in (404, 403):
                with print_lock:
                    print(f"⏭️ SKIP channel={channel_id} offset={offset} -> {r.status_code}")
                return channel_id, offset, None

            if r.status_code in (429, 450, 500, 502, 503):
                if attempt < MAX_RETRIES:
                    with print_lock:
                        print(
                            f"🔁 RETRY {attempt}/{MAX_RETRIES} "
                            f"channel={channel_id} offset={offset} -> {r.status_code}"
                        )
                    time.sleep(RETRY_DELAY * attempt)
                    continue
                else:
                    with print_lock:
                        print(
                            f"❌ FAIL channel={channel_id} offset={offset} "
                            f"after {MAX_RETRIES} retries"
                        )
                    return channel_id, offset, None

            with print_lock:
                print(f"❌ ERROR channel={channel_id} offset={offset} -> {r.status_code}")
            return channel_id, offset, None

        except Exception as e:
            if attempt < MAX_RETRIES:
                with print_lock:
                    print(
                        f"🔁 EXCEPTION RETRY {attempt}/{MAX_RETRIES} "
                        f"channel={channel_id} offset={offset} -> {e}"
                    )
                time.sleep(RETRY_DELAY * attempt)
                continue

            with print_lock:
                print(
                    f"❌ EXCEPTION FAIL channel={channel_id} offset={offset} -> {e}"
                )
            return channel_id, offset, None


# ======================
# MAIN
# ======================
def main():
    start_time = time.time()

    channels = parse_m3u(M3U_FILE)
    if not channels:
        print("❌ No channels loaded. Exiting.")
        return

    tv = ET.Element("tv")

    # 1️⃣ CHANNEL SECTION
    for ch in channels:
        ch_el = ET.SubElement(tv, "channel", {"id": ch["id"]})
        ET.SubElement(ch_el, "display-name").text = ch["name"]
        if ch["logo"]:
            ET.SubElement(ch_el, "icon", {"src": ch["logo"]})

    # 2️⃣ PARALLEL FETCH
    offsets = list(range(0, 4))   # skip -1 (yesterday)
    total_tasks = len(offsets) * len(channels)
    task_index = 0

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {}

        for offset in offsets:
            for ch in channels:
                task_index += 1
                future = executor.submit(
                    fetch_epg, ch["id"], offset, task_index, total_tasks
                )
                future_map[future] = (ch["id"], offset)

        completed = 0

        for future in as_completed(future_map):
            completed += 1
            cid, offset = future_map[future]

            try:
                cid, offset, data = future.result()
            except Exception as e:
                with print_lock:
                    print(f"❌ FUTURE ERROR channel={cid} offset={offset} -> {e}")
                continue

            with print_lock:
                percent = (completed / total_tasks) * 100
                print(
                    f"📊 Progress: {completed}/{total_tasks} "
                    f"({percent:.1f}%)"
                )

            if not data or "epg" not in data:
                continue

            results.append((cid, data))

    # 3️⃣ BUILD PROGRAMMES
    print("\n📺 Building programmes...")

    for cid, data in results:
        for p in data.get("epg", []):
            try:
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

            poster = p.get("episodePoster")
            if poster:
                ET.SubElement(prog, "icon", {"src": SHOW_IMAGE_BASE + poster})

    # 4️⃣ SAVE XMLTV (GZIP)
    xml_data = ET.tostring(tv, encoding="utf-8")

    with gzip.open(OUTPUT_FILE, "wb") as f:
        f.write(xml_data)

    elapsed = time.time() - start_time

    print("\n🎉 DONE (ANTI-BLOCK SAFE)")
    print("📦 Output:", OUTPUT_FILE)
    print("📏 Size:", len(xml_data), "bytes")
    print(f"⏱ Time taken: {elapsed:.2f} seconds")
    print(f"🚀 Threads used: {MAX_WORKERS}")


if __name__ == "__main__":
    main()
