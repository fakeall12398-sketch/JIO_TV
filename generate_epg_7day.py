#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_epg_7day.py
Reads jstar.m3u and writes epg.xml (XMLTV) for N days starting from START_DATE.
Behavior:
 - If env START_DATE_OVERRIDE exists (format "YYYY-MM-DDTHH:MM:SS"), it will be used.
 - Otherwise START_DATE = today's midnight in Asia/Kolkata.
 - Optional env overrides: DAYS (int), SLOT_MINUTES (int).
Outputs:
 - epg.xml
 - epg.xml.gz (gzipped version)
Requires: pytz (install: pip install pytz)
"""

import os
import json
from datetime import datetime, timedelta
import pytz
import xml.etree.ElementTree as ET
import gzip

# --- CONFIG / defaults ---
CHANNELS_FILE = "jstar.m3u"
OUTPUT_FILE = "epg.xml"
OUTPUT_GZ = "epg.xml.gz"

# default values (can be overridden by env)
DEFAULT_DAYS = 7
DEFAULT_SLOT_MINUTES = 30
TZ_NAME = "Asia/Kolkata"

# read overrides from env
env_start = os.getenv("START_DATE_OVERRIDE")  # expected "YYYY-MM-DDTHH:MM:SS"
env_days = os.getenv("DAYS")
env_slot = os.getenv("SLOT_MINUTES")

# set timezone
TZ = pytz.timezone(TZ_NAME)

# compute START_DATE
if env_start:
    try:
        START_DATE = datetime.strptime(env_start, "%Y-%m-%dT%H:%M:%S")
        # make timezone aware in TZ
        START_DATE = TZ.localize(START_DATE)
    except Exception as e:
        print(f"Warning: couldn't parse START_DATE_OVERRIDE='{env_start}': {e}")
        # fallback to today's midnight
        now = datetime.now(TZ)
        START_DATE = now.replace(hour=0, minute=0, second=0, microsecond=0)
else:
    now = datetime.now(TZ)
    START_DATE = now.replace(hour=0, minute=0, second=0, microsecond=0)

# days and slot
try:
    DAYS = int(env_days) if env_days else DEFAULT_DAYS
except:
    DAYS = DEFAULT_DAYS

try:
    SLOT_MINUTES = int(env_slot) if env_slot else DEFAULT_SLOT_MINUTES
except:
    SLOT_MINUTES = DEFAULT_SLOT_MINUTES

# rotating program titles/descs (customize as needed)
PROGRAM_TITLES = [
    "Morning Show", "Daily News", "Prime Drama", "Movie Time", "Kids Hour",
    "Evening Sports", "Music Mix", "Late Night Special", "Documentary Hour",
    "Talk Show"
]
PROGRAM_DESCS = [
    "A lively talk and music show.",
    "Latest news & headlines.",
    "A dramatic serial episode.",
    "Featured movie presentation.",
    "Cartoons and kids entertainment.",
    "Live sports highlights & analysis.",
    "Top chart music videos.",
    "Late-night interviews and features.",
    "A deep-dive documentary.",
    "Celebrity chat and gossip."
]

# --- load channels ---
if not os.path.exists(CHANNELS_FILE):
    print(f"Error: {CHANNELS_FILE} not found in repo root.")
    raise SystemExit(1)

with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
    channels = json.load(f)

# Build XML tree
tv = ET.Element("tv")
tv.set("generator-info-name", "generate_epg_7day.py")

# Add channel nodes (use tvg-id -> id)
for ch in channels:
    tvg_id = ch.get("tvg-id") or ch.get("tvg_id") or ch.get("id") or ch.get("channel-id")
    if not tvg_id:
        # skip if no id
        continue
    channel_el = ET.SubElement(tv, "channel", {"id": str(tvg_id)})
    name = ch.get("channel-name") or ch.get("name") or "Unknown channel"
    dn = ET.SubElement(channel_el, "display-name")
    dn.text = name
    logo = ch.get("tvg-logo") or ch.get("logo")
    if logo:
        # if logo is present, add icon node
        ET.SubElement(channel_el, "icon", {"src": logo})

# Add programme nodes for each channel for each slot
slot_td = timedelta(minutes=SLOT_MINUTES)
for ch in channels:
    tvg_id = ch.get("tvg-id") or ch.get("tvg_id") or ch.get("id") or ch.get("channel-id")
    if not tvg_id:
        continue
    # start from START_DATE (already tz-aware)
    start_dt = START_DATE
    end_dt = start_dt + timedelta(days=DAYS)
    cur = start_dt
    title_idx = 0
    while cur < end_dt:
        start_str = cur.strftime("%Y%m%d%H%M%S %z")
        stop = cur + slot_td
        stop_str = stop.strftime("%Y%m%d%H%M%S %z")
        prog = ET.SubElement(tv, "programme", {
            "start": start_str,
            "stop": stop_str,
            "channel": str(tvg_id)
        })
        t = ET.SubElement(prog, "title", {"lang": "en"})
        t.text = PROGRAM_TITLES[title_idx % len(PROGRAM_TITLES)]
        d = ET.SubElement(prog, "desc", {"lang": "en"})
        d.text = PROGRAM_DESCS[title_idx % len(PROGRAM_DESCS)]
        cat = ET.SubElement(prog, "category", {"lang": "en"})
        cat.text = ch.get("group-title", "General")
        # advance
        cur = stop
        title_idx += 1

# pretty-print helper
def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

indent(tv)
tree = ET.ElementTree(tv)
tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)
print(f"Wrote {OUTPUT_FILE} with EPG for {len(channels)} channels from {START_DATE.strftime('%Y-%m-%d')} for {DAYS} days (slot {SLOT_MINUTES} min).")

# write gzipped version
with open(OUTPUT_FILE, "rb") as f_in:
    with gzip.open(OUTPUT_GZ, "wb") as f_out:
        f_out.writelines(f_in)
print(f"Wrote {OUTPUT_GZ} (gzipped).")
