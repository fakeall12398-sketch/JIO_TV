import re
import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO

def generate_filtered_epg(m3u_file, remote_epg_url, output_file):
    # 1. Get the list of channel IDs from your jstar.m3u
    target_ids = set()
    inf_pattern = re.compile(r'tvg-id="(?P<id>[^"]+)"')
    
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = inf_pattern.search(line)
                if match:
                    target_ids.add(match.group('id'))
        print(f"Found {len(target_ids)} channels in {m3u_file}")
    except FileNotFoundError:
        print(f"Error: {m3u_file} not found.")
        return

    # 2. Download and unzip the jio.xml.gz file
    print(f"Downloading EPG data from {remote_epg_url}...")
    response = requests.get(remote_epg_url)
    if response.status_code != 200:
        print("Failed to download EPG source.")
        return

    with gzip.open(BytesIO(response.content), 'rb') as f:
        tree = ET.parse(f)
        root = tree.getroot()

    # 3. Create a new XML structure
    new_tv = ET.Element('tv', root.attrib)

    # 4. Copy <channel> and <programme> tags ONLY if they match your M3U IDs
    # First, copy the channel definitions
    for channel in root.findall('channel'):
        if channel.get('id') in target_ids:
            new_tv.append(channel)

    # Second, copy the actual programme schedules
    programme_count = 0
    for programme in root.findall('programme'):
        if programme.get('channel') in target_ids:
            new_tv.append(programme)
            programme_count += 1

    # 5. Save the filtered result
    new_tree = ET.ElementTree(new_tv)
    new_tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Successfully generated {output_file} with {programme_count} programmes.")

if __name__ == "__main__":
    M3U_INPUT = 'jstar.m3u'
    # URL found in the first line of your jstar.m3u file
    EPG_SOURCE = 'https://raw.githubusercontent.com/undertaker321/epg/refs/heads/main/jio.xml.gz'
    OUTPUT_XML = 'jstar_epg.xml'
    
    generate_filtered_epg(M3U_INPUT, EPG_SOURCE, OUTPUT_XML)
