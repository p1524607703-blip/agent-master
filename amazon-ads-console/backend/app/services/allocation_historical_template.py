"""Read-only OOXML contract extraction for a SHA256-identified 11-sheet workbook.

Extracting sheet structure never constitutes financial formula approval.
"""
import hashlib
import json
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from .allocation_store import digest

SS="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG="http://schemas.openxmlformats.org/package/2006/relationships"


class HistoricalTemplateError(ValueError):
    pass


def file_sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_historical_xlsx(path, expected_sha256, *, expected_sheets=11):
    path=Path(path)
    if not path.is_file() or path.suffix.lower()!=".xlsx":
        raise HistoricalTemplateError("ORIGINAL_XLSX_NOT_FOUND")
    observed_sha=file_sha256(path)
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or observed_sha!=expected_sha256:
        raise HistoricalTemplateError("HISTORICAL_SHA256_MISMATCH")
    try:
        with zipfile.ZipFile(path) as archive:
            root=ET.fromstring(archive.read("xl/workbook.xml"))
            relation_root=ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rels={row.get("Id"):row.get("Target") for row in relation_root.findall("{"+PKG+"}Relationship")}
            names=root.findall("{"+SS+"}sheets/{"+SS+"}sheet")
            if len(names)!=expected_sheets:
                raise HistoricalTemplateError("HISTORICAL_SHEET_COUNT_MISMATCH")
            shared=[]
            if "xl/sharedStrings.xml" in archive.namelist():
                with archive.open("xl/sharedStrings.xml") as stream:
                    for _,node in ET.iterparse(stream,events=("end",)):
                        if node.tag=="{"+SS+"}si":
                            shared.append("".join(child.text or "" for child in node.iter("{"+SS+"}t")))
                            node.clear()
            sheets=[]
            for entry in names:
                name=entry.get("name")
                rel=rels.get(entry.get("{"+R+"}id"))
                if not rel:
                    raise HistoricalTemplateError("SHEET_RELATION_MISSING")
                target=(rel.lstrip("/") if rel.startswith("/") else posixpath.normpath("xl/"+rel))
                if target not in archive.namelist():
                    raise HistoricalTemplateError("SHEET_PART_MISSING")
                dimension=None
                row_count=0
                formula_count=0
                first_rows=[]
                with archive.open(target) as stream:
                    for _,element in ET.iterparse(stream,events=("end",)):
                        if element.tag=="{"+SS+"}dimension":
                            dimension=element.get("ref")
                        elif element.tag=="{"+SS+"}row":
                            row_count+=1
                            if len(first_rows)<2:
                                cells={}
                            for cell in element.findall("{"+SS+"}c"):
                                formula_count+=len(cell.findall("{"+SS+"}f"))
                                if len(first_rows)<2:
                                    val=cell.find("{"+SS+"}v")
                                    inline=cell.find("{"+SS+"}is")
                                    cvalue=None
                                    if val is not None:
                                        cvalue=val.text
                                        if cell.get("t")=="s" and cvalue is not None:
                                            idx=int(cvalue)
                                            cvalue=shared[idx] if idx<len(shared) else None
                                    elif inline is not None:
                                        cvalue="".join(t.text or "" for t in inline.iter("{"+SS+"}t"))
                                    if cvalue is not None:
                                        cells[cell.get("r")]=str(cvalue)[:160]
                            if len(first_rows)<2:
                                first_rows.append({"row":int(element.get("r","0")),
                                                   "cells":cells})
                            element.clear()
                sheets.append({"name":name,"dimension":dimension,
                               "xml_row_elements":row_count,"formula_cells":formula_count,
                               "first_two_rows":first_rows})
    except (zipfile.BadZipFile,KeyError,ET.ParseError,ValueError,IndexError) as ex:
        if isinstance(ex,HistoricalTemplateError):
            raise
        raise HistoricalTemplateError("OOXML_STRUCTURE_INVALID") from ex
    result={"source":"SHA256_VERIFIED_HISTORICAL_XLSX",
            "file_name":path.name,"file_bytes":path.stat().st_size,
            "sha256":observed_sha,"sheet_count":len(sheets),"sheets":sheets,
            "file_identity_verified":True,"sheet_structure_extracted":True,
            "formula_semantics_approved":False,
            "business_authority_approved":False,"financial_replay_completed":False,
            "may_publish":False}
    result["contract_hash"]=digest(result)
    return result


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Offline 11-sheet OOXML identity, not approval")
    parser.add_argument("path")
    parser.add_argument("--sha256",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    result=inspect_historical_xlsx(args.path,args.sha256)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
