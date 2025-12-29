import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

def generate_epg(m3u_file, output_file):
    # Root element for the EPG
    tv = ET.Element('tv')

    # Regex to extract tvg-id, tvg-logo, and display name from #EXTINF lines
    # Example line: #EXTINF:-1 tvg-id="1069" group-title="Education" tvg-logo="url",Vande Gujarat 1
    inf_pattern = re.compile(r'#EXTINF:.*tvg-id="(?P<id>[^"]+)".*tvg-logo="(?P<logo>[^"]+)".*,(?P<name>.+)')

    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = inf_pattern.search(line)
                if match:
                    channel_id = match.group('id')
                    logo_url = match.group('logo')
                    display_name = match.group('name').strip()

                    # Create XML structure for each channel
                    channel = ET.SubElement(tv, 'channel', id=channel_id)
                    name_elem = ET.SubElement(channel, 'display-name')
                    name_elem.text = display_name
                    ET.SubElement(channel, 'icon', src=logo_url)

        # Pretty print the XML
        xml_string = ET.tostring(tv, encoding='utf-8')
        reparsed = minidom.parseString(xml_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        with open(output_file, "w", encoding='utf-8') as f:
            f.write(pretty_xml)
        print(f"Successfully generated {output_file}")

    except FileNotFoundError:
        print(f"Error: {m3u_file} not found.")

if __name__ == "__main__":
    generate_epg('jstar.m3u', 'jstar_epg.xml')
  
