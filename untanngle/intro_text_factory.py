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
        self.xml_id_attrib = "{http://www.w3.org/XML/1998/namespace}id"

    def merge_intro_text_files(self) -> list[str]:
        elements = [[], [], [], []]
        for i, name in enumerate(self.intro_text_files):
            path = f"{self.input_xml_directory}/{name}.xml"
            if os.path.exists(path):
                logger.info(f"<= {path}")
                tree = ET.parse(path)
                root = tree.getroot()

                elements[0].extend(
                    [self._with_adjusted_ids(e, i + 1) for e in (root.find(".//div[@xml:lang='nl']", self.ns))]
                )
                elements[1].extend(
                    [self._with_adjusted_ids(e, i + 1) for e in (root.find(".//div[@xml:lang='en']", self.ns))]
                )

                notes_nl = root.find(".//listAnnotation[@xml:lang='nl']", self.ns)
                if notes_nl:
                    elements[2].extend([self._with_adjusted_ids(e, i + 1) for e in notes_nl])

                notes_en = root.find(".//listAnnotation[@xml:lang='en']", self.ns)
                if notes_en:
                    elements[3].extend([self._with_adjusted_ids(e, i + 1) for e in notes_en])
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
        standoff = ET.SubElement(tei, "standOff")

        div_intro_nl = self._build_section_div("intro-nl", "nl", elements[0])
        body.append(div_intro_nl)

        div_intro_en = self._build_section_div("intro-en", "en", elements[1])
        body.append(div_intro_en)

        list_annotation_notes_nl = self._build_list_annotation("nl", elements[2])
        standoff.append(list_annotation_notes_nl)

        list_annotation_notes_en = self._build_list_annotation("en", elements[3])
        standoff.append(list_annotation_notes_en)

        return tei

    @staticmethod
    def _build_section_div(div_type: str, lang: str, elements: list[ET.Element]):
        div = ET.Element("div", attrib={"xml:lang": lang, "type": div_type})
        for element in elements:
            div.append(element)
        return div

    @staticmethod
    def _build_list_annotation(lang: str, elements: list[ET.Element]):
        div = ET.Element("listAnnotation", attrib={"xml:lang": lang, "type": "notes"})
        for element in elements:
            div.append(element)
        return div

    def _with_adjusted_ids(self, e: ET.Element, i: int) -> ET.Element:
        for ptr in e.findall(".//ptr", namespaces=self.ns):
            ptr.set("target", ptr.attrib["target"].replace("note", f"section.{i}.note"))
        if self.xml_id_attrib in e.attrib:
            e.set(self.xml_id_attrib, f"section.{i}." + e.attrib[self.xml_id_attrib])
            if "n" in e.attrib and "note" in e.attrib[self.xml_id_attrib]:
                e.set("n", f"{i}-{e.attrib['n']}")
        for element in e.findall(".//*[@xml:id]", namespaces=self.ns):
            element.set(self.xml_id_attrib, f"section.{i}." + element.attrib[self.xml_id_attrib])
        if "corresp" in e.attrib:
            e.set("corresp", e.attrib["corresp"].replace('#', f"#section.{i}."))
        for element in e.findall(".//*[@corresp]", namespaces=self.ns):
            element.set("corresp", element.attrib["corresp"].replace('#', f"#section.{i}."))

        return e
