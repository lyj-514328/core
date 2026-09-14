"""Generate a small DOCX with text that must survive PDF conversion."""

import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

EXPECTED_TEXT = ['Converter smoke test', '\u4e2d\u6587\u6587\u6863\u8f6c\u6362\u6d4b\u8bd5', '12345.67']


def create_document(path):
    word_ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    document = ET.Element(f'{{{word_ns}}}document')
    body = ET.SubElement(document, f'{{{word_ns}}}body')
    for text in EXPECTED_TEXT:
        paragraph = ET.SubElement(body, f'{{{word_ns}}}p')
        run = ET.SubElement(paragraph, f'{{{word_ns}}}r')
        ET.SubElement(run, f'{{{word_ns}}}t').text = text
    types_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
    types = ET.Element(f'{{{types_ns}}}Types')
    ET.SubElement(types, f'{{{types_ns}}}Default', Extension='rels',
                  ContentType='application/vnd.openxmlformats-package.relationships+xml')
    ET.SubElement(types, f'{{{types_ns}}}Override', PartName='/word/document.xml',
                  ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml')
    rels_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    relationships = ET.Element(f'{{{rels_ns}}}Relationships')
    ET.SubElement(relationships, f'{{{rels_ns}}}Relationship', Id='rId1',
                  Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
                  Target='word/document.xml')
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        for name, root, namespace, prefix in (
            ('[Content_Types].xml', types, types_ns, ''),
            ('_rels/.rels', relationships, rels_ns, ''),
            ('word/document.xml', document, word_ns, 'w'),
        ):
            ET.register_namespace(prefix, namespace)
            archive.writestr(name, ET.tostring(root, encoding='utf-8', xml_declaration=True))
