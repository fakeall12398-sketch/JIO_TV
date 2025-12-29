import re
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

def fetch_jiotv_epg():
    m3u_file = 'jstar.m3u'
    output_file = 'jstar_epg.xml'
    api_url_template = "https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get?channel_id={}"
    
    # Root element for EPG
    tv = ET.Element('tv')

    # 1. Parse M3U for IDs, Logos, and Names
    # Matches: tvg-id="1069" ... tvg-logo="url",Channel Name
    pattern = re.compile(r'tvg-id="(?P<id>\d+)".*tvg-logo="(?P<logo>[^"]+)".*,(?P<name>.+)')
    
    channels = []
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    channels.append(match.groupdict())
    except FileNotFoundError:
        print(f"Error: {m3u_file} not found.")
        return

    # 2. Fetch data for each channel
    for ch in channels:
        ch_id = ch['id']
        print(f"Fetching EPG for {ch['name']} (ID: {ch_id})...")
        
        # Add channel metadata to XML
        channel_node = ET.SubElement(tv, 'channel', id=ch_id)
        ET.SubElement(channel_node, 'display-name').text = ch['name'].strip()
        ET.SubElement(channel_node, 'icon', src=ch['logo'])

        # Fetch live programme data from API
        try:
            response = requests.get(api_url_template.format(ch_id), timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Assuming the API returns a list of programmes in 'epg' key
                for item in data.get('epg', []):
                    # Convert timestamps if necessary or use provided ones
                    prog = ET.SubElement(tv, 'programme', {
                        'start': item.get('startEpoch', ''),
                        'stop': item.get('endEpoch', ''),
                        'channel': ch_id
                    })
                    ET.SubElement(prog, 'title').text = item.get('showname', 'No Title')
                    ET.SubElement(prog, 'desc').text = item.get('description', '')
                    ET.SubElement(prog, 'category').text = item.get('showCategory', '')
                    if item.get('episode_num'):
                        ET.SubElement(prog, 'episode-num', system="xmltv_ns").text = str(item.get('episode_num'))
                    if item.get('episode_poster'):
                        ET.SubElement(prog, 'icon', src=item.get('episode_poster'))
            else:
                print(f"  Failed to fetch programmes for {ch_id}")
        except Exception as e:
            print(f"  Error fetching {ch_id}: {e}")

    # 3. Save formatted XML
    xml_str = minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    print(f"\nSuccessfully generated {output_file}")

if __name__ == "__main__":
    fetch_jiotv_epg()
