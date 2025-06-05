import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from loguru import logger


@dataclass
class IntroTextConfig:
    intro_text_files: list[str]
    input_xml_directory: str
    output_xml_directory: str


class IntroTextFactory:
    def __init__(self, config: IntroTextConfig):
        self.intro_text_files = config.intro_text_files
        self.input_xml_directory = config.input_xml_directory.removesuffix("/")
        self.output_xml_directory = config.output_xml_directory.removesuffix("/")
        self.errors = []
        self.ns = {
            "xml": "http://www.w3.org/XML/1998/namespace",
            "": "http://www.tei-c.org/ns/1.0"
        }

    def merge_intro_text_files(self) -> list[str]:
        elements = [[], [], [], []]
        for i, name in enumerate(self.intro_text_files):
            path = f"{self.input_xml_directory}/{name}.xml"
            if os.path.exists(path):
                logger.info(f"<= {path}")
                tree = ET.parse(path)
                root = tree.getroot()

                elements[0].extend(
                    [self._with_adjusted_note_ids(e, i + 1) for e in (root.find(".//div[@xml:lang='nl']", self.ns))]
                )
                elements[1].extend(
                    [self._with_adjusted_note_ids(e, i + 1) for e in (root.find(".//div[@xml:lang='en']", self.ns))]
                )

                notes_nl = root.find(".//listAnnotation[@xml:lang='nl']", self.ns)
                if notes_nl:
                    elements[2].extend([self._with_adjusted_note_ids(e, i + 1) for e in notes_nl])

                notes_en = root.find(".//listAnnotation[@xml:lang='en']", self.ns)
                if notes_en:
                    elements[3].extend([self._with_adjusted_note_ids(e, i + 1) for e in notes_en])
            else:
                self.errors.append(f"expected file {path} not found")

        tei = self._build_intro_tei(elements)
        merged_xml = ET.tostring(tei, encoding="utf-8").decode("utf-8").replace("ns0:", "").replace(":ns0", "")

        if not os.path.exists(self.output_xml_directory):
            os.makedirs(self.output_xml_directory)

        path = f"{self.output_xml_directory}/introduction.xml"
        logger.info(f"=> {path}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(merged_xml)

        return self.errors

    def _build_intro_tei(self, elements):
        tei = ET.Element("TEI")

        text = ET.SubElement(tei, "text")
        body = ET.SubElement(text, "body")

        div_intro_nl = self._build_section_div("intro-nl", "nl", elements[0])
        body.append(div_intro_nl)

        div_intro_en = self._build_section_div("intro-en", "en", elements[1])
        body.append(div_intro_en)

        div_notes_nl = self._build_section_div("notes-nl", "nl", elements[2])
        body.append(div_notes_nl)

        div_notes_en = self._build_section_div("notes-en", "en", elements[3])
        body.append(div_notes_en)

        return tei

    @staticmethod
    def _build_section_div(div_type: str, lang: str, elements: list[ET.Element]):
        div = ET.Element("div", attrib={"xml:lang": lang, "type": div_type})
        for element in elements:
            div.append(element)
        return div

    def _with_adjusted_note_ids(self, e: ET.Element, i: int) -> ET.Element:
        for ptr in e.findall(".//ptr", namespaces=self.ns):
            ptr.set("target", ptr.attrib["target"].replace("note", f"note.{i}"))
        if "{http://www.w3.org/XML/1998/namespace}id" in e.attrib:
            e.set("{http://www.w3.org/XML/1998/namespace}id",
                  e.attrib["{http://www.w3.org/XML/1998/namespace}id"].replace("note", f"note.{i}"))
            if "n" in e.attrib and "note" in e.attrib["{http://www.w3.org/XML/1998/namespace}id"]:
                e.set("n", f"{i}-{e.attrib['n']}")
        return e
