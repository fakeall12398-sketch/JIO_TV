import re
import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO

def generate_full_epg():
    m3u_file = 'jstar.m3u'
    remote_epg_url = 'https://raw.githubusercontent.com/undertaker321/epg/refs/heads/main/jio.xml.gz'
    output_file = 'jstar_epg.xml'

    # 1. Collect all tvg-ids from your M3U
    target_ids = set()
    # Matches tvg-id="123"
    id_pattern = re.compile(r'tvg-id="(?P<id>[^"]+)"')
    
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = id_pattern.search(line)
                if match:
                    target_ids.add(match.group('id'))
        print(f"Filtering EPG for {len(target_ids)} channels...")
    except FileNotFoundError:
        print(f"Error: {m3u_file} not found.")
        return

    # 2. Download and Extract Remote EPG
    print(f"Downloading source EPG...")
    response = requests.get(remote_epg_url)
    if response.status_code != 200:
        print("Failed to download EPG source.")
        return

    with gzip.open(BytesIO(response.content), 'rb') as f:
        # Use iterparse for high performance with large XML files
        context = ET.iterparse(f, events=('start', 'end'))
        _, root = next(context) # Get root element

        # Create new XML structure
        new_tv = ET.Element('tv', root.attrib)

        for event, elem in context:
            if event == 'end':
                # Filter <channel> tags
                if elem.tag == 'channel':
                    if elem.get('id') in target_ids:
                        new_tv.append(elem)
                    else:
                        root.clear() # Free memory
                
                # Filter <programme> tags (This contains the schedule data)
                elif elem.tag == 'programme':
                    if elem.get('channel') in target_ids:
                        new_tv.append(elem)
                    else:
                        root.clear() # Free memory

        # 3. Write final file
        tree = ET.ElementTree(new_tv)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"Done! Created {output_file}")

if __name__ == "__main__":
    generate_full_epg()
