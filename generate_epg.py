import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time

def format_date(timestamp_ms):
    """Converts Jio API milliseconds to XMLTV format: YYYYMMDDHHMMSS +0530"""
    # JioTV provides time in milliseconds
    dt = datetime.fromtimestamp(int(timestamp_ms) / 1000)
    return dt.strftime('%Y%m%d%H%M%S +0530')

def generate_epg():
    m3u_file = 'jstar.m3u'
    output_file = 'jstar_epg.xml'
    # offset=0 is today's schedule
    api_url = "https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get?channel_id={}&offset=0"
    
    # Headers are MANDATORY to prevent the API from blocking the request
    headers = {
        'User-Agent': 'JioTV',
        'host': 'jiotvapi.cdn.jio.com'
    }

    # Initialize XML Root
    root = ET.Element('tv', {
        'generator-info-name': 'JStar-EPG-Gen',
        'source-info-name': 'JioTV API'
    })

    # 1. Parse M3U for Channel IDs, Logos, and Names
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            m3u_content = f.read()
    except FileNotFoundError:
        print(f"Error: {m3u_file} not found in root directory.")
        return

    # Regular expression to find tvg-id, logo, and channel name
    channels = re.findall(r'tvg-id="(\d+)".*tvg-logo="([^"]+)".*,(.*)', m3u_content)

    if not channels:
        print("No channels found in M3U. Check your tvg-id tags.")
        return

    # 2. Process each channel
    for ch_id, ch_logo, ch_name in channels:
        ch_name = ch_name.strip()
        print(f"Fetching: {ch_name} (ID: {ch_id})...")

        # Add Channel metadata to XML
        channel_node = ET.SubElement(root, 'channel', id=ch_id)
        ET.SubElement(channel_node, 'display-name').text = ch_name
        ET.SubElement(channel_node, 'icon', src=ch_logo)

        # 3. Fetch Program Data from API
        try:
            resp = requests.get(api_url.format(ch_id), headers=headers, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                programmes = data.get('epg', [])
                
                for item in programmes:
                    prog = ET.SubElement(root, 'programme', {
                        'start': format_date(item['startEpoch']),
                        'stop': format_date(item['endEpoch']),
                        'channel': ch_id
                    })
                    ET.SubElement(prog, 'title').text = item.get('showname', 'No Title')
                    ET.SubElement(prog, 'desc').text = item.get('description', 'No description available.')
                    ET.SubElement(prog, 'category').text = item.get('showCategory', 'General')
                    
                    # Add Poster/Thumbnail if available
                    if item.get('episode_poster'):
                        poster = f"https://jiotv.catchup.cdn.jio.com/dare_images/shows/{item['episode_poster']}"
                        ET.SubElement(prog, 'icon', src=poster)
                
                print(f"  Done: Added {len(programmes)} programs.")
            else:
                print(f"  Failed: HTTP {resp.status_code}")
                
            # Anti-ban delay: Sleep for 0.3 seconds between requests
            time.sleep(0.3)

        except Exception as e:
            print(f"  Error fetching ID {ch_id}: {e}")

    # 4. Save the Final XML
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0) # Make XML readable
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"\nSuccess! EPG saved to {output_file}")

if __name__ == "__main__":
    generate_epg()
