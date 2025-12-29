import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time

def format_date(timestamp_ms):
    """Converts milliseconds timestamp to XMLTV format: 20231229153000 +0530"""
    # JioTV timestamps are in milliseconds
    dt = datetime.fromtimestamp(int(timestamp_ms) / 1000)
    return dt.strftime('%Y%m%d%H%M%S +0530')

def generate_epg():
    m3u_file = 'jstar.m3u'
    output_file = 'jstar_epg.xml'
    # offset=0 is today, offset=1 is tomorrow
    api_url = "https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get?channel_id={}&offset=0"
    
    # Headers are REQUIRED to prevent the "Failed to fetch" error
    headers = {
        'User-Agent': 'JioTV',
        'host': 'jiotvapi.cdn.jio.com'
    }

    root = ET.Element('tv')

    # 1. Parse M3U for IDs
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            m3u_content = f.read()
    except FileNotFoundError:
        print(f"Error: {m3u_file} not found.")
        return

    # Extract ID, Logo, and Name
    channels = re.findall(r'tvg-id="(\d+)".*tvg-logo="([^"]+)".*,(.*)', m3u_content)

    for ch_id, ch_logo, ch_name in channels:
        ch_name = ch_name.strip()
        print(f"Fetching: {ch_name} (ID: {ch_id})...")

        # Add Channel metadata to XML
        channel_node = ET.SubElement(root, 'channel', id=ch_id)
        ET.SubElement(channel_node, 'display-name').text = ch_name
        ET.SubElement(channel_node, 'icon', src=ch_logo)

        # 2. Fetch Data with Headers
        try:
            resp = requests.get(api_url.format(ch_id), headers=headers, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                # JioTV API returns programmes in the 'epg' key
                programmes = data.get('epg', [])
                
                for item in programmes:
                    prog = ET.SubElement(root, 'programme', {
                        'start': format_date(item['startEpoch']),
                        'stop': format_date(item['endEpoch']),
                        'channel': ch_id
                    })
                    ET.SubElement(prog, 'title').text = item.get('showname', 'No Title')
                    ET.SubElement(prog, 'desc').text = item.get('description', '')
                    ET.SubElement(prog, 'category').text = item.get('showCategory', 'General')
                    
                    # Episode details
                    if item.get('episode_num'):
                        ET.SubElement(prog, 'episode-num', system="xmltv_ns").text = str(item.get('episode_num'))
                    
                    # Show Poster
                    if item.get('episode_poster'):
                        poster_url = f"https://jiotv.catchup.cdn.jio.com/dare_images/shows/{item['episode_poster']}"
                        ET.SubElement(prog, 'icon', src=poster_url)
                
                print(f"  Successfully added {len(programmes)} programs.")
            else:
                print(f"  Failed! HTTP Status: {resp.status_code}")
                
            # Anti-Ban: Small delay between requests
            time.sleep(0.2)

        except Exception as e:
            print(f"  Error: {e}")

    # 3. Save the XML
    tree = ET.ElementTree(root)
    # Use built-in indent for Python 3.9+
    ET.indent(tree, space="  ", level=0)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"\nCompleted! Generated {output_file}")

if __name__ == "__main__":
    generate_epg()
