from __future__ import annotations

import datetime
import json
from typing import List

from flask_babel import lazy_gettext as _

class OAStatus:
    key:str
    label:str

    def __init__(self,key,label):
        self.key = key
        self.label = label

OASTATUS_HYBRID = OAStatus('hybrid',_('Hybrid'))
OASTATUS_GOLD = OAStatus('gold',_('Gold'))
#OASTATUS_DIAMOND = OAStatus('diamond',_('Diamond'))
#OASTATUS_TBC_GOLD = OAStatus('tbc_gold',_('TBC Gold'))
OASTATUS_GOLD_HYBRID = OAStatus('gold_hybrid',_('Gold & Hybrid'))

OASTATUS = {
    OASTATUS_HYBRID.key: OASTATUS_HYBRID,
    OASTATUS_GOLD.key: OASTATUS_GOLD,
#    OASTATUS_DIAMOND.key: OASTATUS_DIAMOND,
    #OASTATUS_TBC_GOLD.key: OASTATUS_TBC_GOLD,
    OASTATUS_GOLD_HYBRID.key: OASTATUS_GOLD_HYBRID,
}


class ApplicationRequirement:
    key:str
    label:str

    def __init__(self,key,label):
        self.key = key
        self.label = label

APPREQ_REQUIRED = ApplicationRequirement('required',_('Antrag erforderlich'))
APPREQ_NOT_REQUIRED = ApplicationRequirement('not required',_('kein Antrag erforderlich'))

APPLICATION_REQUIREMENT = {
    APPREQ_REQUIRED.key: APPREQ_REQUIRED,
    APPREQ_NOT_REQUIRED.key: APPREQ_NOT_REQUIRED,
}

class LinkType:
    key:str
    label:str
    sort: int

    def __init__(self,key,label,sort):
        self.key = key
        self.label = label
        self.sort = sort

LINKTYPE_PUBLISHER = LinkType('publisher',_('Verlag'),0)
LINKTYPE_WORKFLOW = LinkType('workflow',_('Workflow'),1)
LINKTYPE_TITLES_HTML = LinkType('titles_html',_('Titel (html)'),2)
LINKTYPE_TITLES_PDF = LinkType('titles_pdf',_('Titel (pdf)'),3)
LINKTYPE_TITLES_XLSX = LinkType('titles_xlsx',_('Titel (xlsx)'),4)

LINKTYPE = {
    LINKTYPE_PUBLISHER.key: LINKTYPE_PUBLISHER,
    LINKTYPE_WORKFLOW.key: LINKTYPE_WORKFLOW,
    LINKTYPE_TITLES_HTML.key: LINKTYPE_TITLES_HTML,
    LINKTYPE_TITLES_PDF.key: LINKTYPE_TITLES_PDF,
    LINKTYPE_TITLES_XLSX.key: LINKTYPE_TITLES_XLSX,
}

class Setting:
    id: int
    name: str
    value: str 
    value_en: str
    value_de: str
    
    def __init__ (self):
        self.id = None
        self.name = None
        self.value = None
        self.value_en = None
        self.value_de = None

    def toDict(self):
        d = {}
        d['id'] = self.id
        d['name'] = self.name
        d['value'] = self.value
        d['value_en'] = self.value_en
        d['value_de'] = self.value_de
        return d

    def toJson(self):
        return json.dumps(self.toDict())


class Journal:
    id:int
    title:str
    url:str 
    print_issn:str
    e_issn:str
    valid_till:datetime.date
    publisher:Publisher
    
    def __init__ (self):
        self.id = None
        self.title = None
        self.url = None
        self.print_issn = None
        self.e_issn = None
        self.valid_till = None
        self.publisher = None

    def toDict(self):
        d = {}
        d['id'] = self.id
        d['title'] = self.title
        d['url'] = self.url
        d['print_issn'] = self.print_issn
        d['e_issn'] = self.e_issn
        d['valid_till'] = self.valid_till.isoformat()
        d['publisher'] = self.publisher.toDict()
        return d

    def toJson(self):
        return json.dumps(self.toDict())

    # checks if the relevant properties of journal have changed
    # treat None and '' as identical
    def getDifferences(self,other: Journal) -> dict[str,List[str]]:
        diffs = {}
        if (self.title or other.title) and self.title.strip() != other.title.strip(): diffs['title'] = (self.title,other.title)
        if (self.url or other.url) and self.url != other.url: diffs['url'] = (self.url,other.url)
        if (self.print_issn or other.print_issn) and self.print_issn != other.print_issn: diffs['print_issn'] = (self.print_issn,other.print_issn)
        if (self.e_issn or other.e_issn) and self.e_issn != other.e_issn: diffs['e_issn'] = (self.e_issn,other.e_issn)
        return diffs

class Link:
    id:int
    publisher:Publisher
    link:str
    linktype:LinkType
    linktext_de:str
    linktext_en:str

    def __init__ (self):
        self.id = None
        self.publisher = None
        self.link = None
        self.linktype = None
        self.linktext_de = None
        self.linktext_en = None
    
    def __lt__(self,other):
        return True if self.linktype.sort < other.linktype.sort else False

class Excel:
    id:int
    name:str
    file:bytes
    uploaded:datetime.datetime
    valid:datetime.date
    publisher:Publisher

    def __init__ (self):
        self.id = None
        self.name = None
        self.file = None
        self.uploaded = None
        self.valid = None
        self.publisher = None

    def __eq__(self,other):
        return True if self.id == other.id else False

    def __lt__(self,other):
        if self.id < other.id: return True

class Publisher:
    id:int
    name:str
    validity:str
    oa_status:OAStatus
    application_requirement:ApplicationRequirement
    funder_info:str
    cost_coverage:str
    valid_tu:str
    article_type:str
    further_info:str
    funder_info_en:str
    cost_coverage_en:str
    valid_tu_en:str
    article_type_en:str
    further_info_en:str
    links:List[Link]
    is_doaj:int
    doaj_linked:int

    def __init__ (self):
        self.id = None
        self.name = None
        self.validity = None
        self.oa_status = None
        self.application_requirement = None
        self.funder_info = None
        self.cost_coverage = None
        self.valid_tu = None
        self.article_type = None
        self.further_info = None
        self.funder_info_en = None
        self.cost_coverage_en = None
        self.valid_tu_en = None
        self.article_type_en = None
        self.further_info_en = None
        self.is_doaj = None
        self.doaj_linked = None
        self.links = []

    def toDict(self):
        d = {}
        d['id'] = self.id
        d['name'] = self.name
        d['validity'] = self.validity
        d['oa_status'] = self.oa_status.key if self.oa_status else None
        d['application_requirement'] = self.application_requirement.key if self.application_requirement else None
        d['funder_info'] = self.funder_info
        d['cost_coverage'] = self.cost_coverage
        d['valid_tu'] = self.valid_tu
        d['article_type'] = self.article_type
        d['further_info'] = self.further_info
        d['funder_info_en'] = self.funder_info_en
        d['cost_coverage_en'] = self.cost_coverage_en
        d['valid_tu_en'] = self.valid_tu_en
        d['article_type_en'] = self.article_type_en
        d['further_info_en'] = self.further_info_en
        d['is_doaj'] = self.is_doaj
        d['doaj_linked'] = self.doaj_linked
        x = []
        d['links'] = x
        for l in self.links:
            y = {}
            y['id'] = l.id
            y['link'] = l.link   
            y['linktype'] = l.linktype.key if l.linktype else None
            y['linktext_de'] = l.linktext_de
            y['linktext_en'] = l.linktext_en
            x.append(y)
        return d

    def toJson(self):
        return json.dumps(self.toDict())
    
    def __eq__(self,other):
        return True if self.id == other.id else False
    
    def __lt__(self,other):
        if self.name < other.name: return True
        if self.name > other.name: return False
        if not self.oa_status and not other.oa_status: return False
        if not self.oa_status and other.oa_status: return True
        if self.oa_status and not other.oa_status: return False
        return True if self.oa_status.key < other.oa_status.key else False
    
    def __str__(self):
        s = self.name
        if self.oa_status:
            s += ' (' + self.oa_status.label + ')'
        return s
