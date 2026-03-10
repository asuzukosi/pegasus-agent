import re


class XMLProcessor:
    def __init__(self):
        pass

    def process(self, xml_file: str) -> str:
        with open(xml_file, 'r') as file:
            xml_data = file.read()
        return xml_data

    @staticmethod
    def extract_data(self, xml_data: str, tag: str) -> dict:
        match = re.search(f'<{tag}>(.*?)</{tag}>', xml_data)
        if match:
            return match.group(1)
        return None