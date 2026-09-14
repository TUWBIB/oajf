import io
import os
import gzip
import re
import tempfile
import traceback
import datetime
from functools import wraps
from typing import List, Tuple

import requests
import openpyxl
import csv

from flask import g, current_app as app, request
from flask_babel import lazy_gettext as _

from oajf.db import readPublishers as db_readPublishers
from oajf.db import readSettings as db_readSettings
from oajf.models import Journal

# Default GeoIP source: DB-IP dbip-country-lite (CC-BY-4.0, monthly updates).
# Used when no geoip_link setting / --url is configured.
# The URL is versioned by year/month; the {YYYY} and {MM} placeholders are
# replaced with the current date before the request is made.
DEFAULT_GEOIP_URL = "https://download.db-ip.com/free/dbip-country-lite-{YYYY}-{MM}.csv.gz"

def logfunc(f):
    from oajf.db import getPoolStats
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = None
        try:
            session_id = request.cookies.get(app.config["SESSION_COOKIE_NAME"])            
        except Exception as e:
            pass
        free, used, has_pool = getPoolStats()
        if has_pool:
            app.logger.debug(f'*** {f.__name__}, free: {free}, used: {used}, session {session_id}')
        else:
            app.logger.debug(f'*** {f.__name__}, session {session_id}')
        retval = None
        try:
            retval = f(*args, **kwargs)
        except Exception as e:
            app.logger.error(e)
            app.logger.error(traceback.format_exc())
            raise e
        free, used, has_pool = getPoolStats()
        if has_pool:
            app.logger.debug(f'--- {f.__name__}, free: {free}, used: {used}, session {session_id}')
        else:
            app.logger.debug(f'--- {f.__name__}, session {session_id}')
        return retval
    return decorated_function


@logfunc
def get_publishers(force_reload=False):
    publishers = getattr(g, 'publishers', None)
    if publishers is None or force_reload:
        publishers, m_publishers = db_readPublishers()

        g.publishers = publishers
        g.m_publishers = m_publishers
        
    return publishers

@logfunc
def get_settings(force_reload=False):
    l_setting = getattr(g, 'l_setting', None)
    if l_setting is None or force_reload:
        l_setting = db_readSettings()
        g.l_setting = l_setting
        m_id_setting = {}
        m_name_setting = {}
        for o in l_setting:
            m_id_setting[o.id] = o
            m_name_setting[o.name] = o

        g.l_setting = l_setting
        g.m_id_setting = m_id_setting
        g.m_name_setting = m_name_setting
        
    return l_setting

def getSettingValue(name):
    get_settings()
    x = g.m_name_setting.get(name,None)
    return x.value if x else None

def getSettingValueLang(name,lang):
    val = None
    get_settings()
    x = g.m_name_setting.get(name,None)
    if x:
        val = getattr(x,'value_'+lang,None)
    
    return val


def getDOAJChangesFileAsExcelWorkbook(url=None) -> Tuple[openpyxl.workbook.Workbook,io.BytesIO,List[str]]:
    """
    fetches the DOAJ-changes file from Google-Docs and returns it as parsed openpyxl Workbook together with the raw bytes
    also checks the file for conformance to the expected format
    """
    errs = []
    wb = None
    data = None

    if not url:
        url = getSettingValue('doaj_changes_link')
    if not url:
        errs.append(_("URL für DOAJ-Änderungen nicht gesetzt."))
        return [],errs

    try:
        r = requests.get(url, allow_redirects=True)
    except Exception as e:
        app.logger.error(f"exception={type(e).__name__}")
        app.logger.error(f"stacktrace={traceback.format_exc()}")
        errs.append(_(f"Fehler beim Holen der DOAJ-Änderungen."))
        errs.append(e)
        return wb,data,errs

    try:
        data = io.BytesIO(r.content)
        data.seek(0)
        wb = openpyxl.load_workbook(filename=data)
    except Exception as e:
        errs.append(_(f"Fehler beim Parsen der DOAJ-Änderungen."))
        errs.append(e)
        return wb,data,errs

    try:
        sheet = wb['Withdrawn']
        vals = []
        for i in range(1,5):
            val = sheet.cell(7,i).value
            if val: val = str(val).strip()
            vals.append(val)
        if (
            vals[0] != 'Journal Title' or
            vals[1] != 'ISSN' or
            vals[2] != 'Date Removed (dd/mm/yyyy)' or
            vals[3] != 'Reason'
        ):
            errs.append("sheet 'Withdrawn' does not conform to the expected format")
            return wb,data,errs
        
        sheet = wb['Added']
        vals = []
        for i in range(1,4):
            val = sheet.cell(6,i).value
            if val: val = str(val).strip()
            vals.append(val)
        if (
            vals[0] != 'Journal Title' or
            vals[1] != 'ISSN' or
            vals[2] != 'Date Added'
        ):
            errs.append(_(f"Das sheet 'Added' entspricht nicht dem erwarteten Format."))
            return wb,data,errs
    except Exception as e:
        errs.append(_(f"Fehler beimn Prüfen des Formats der DOAJ-Änderungen."))
        errs.append(e)
    
        return wb,data,errs

    return wb,data,errs


def getDOAJDump(url=None) -> Tuple[List[Journal],List[str]]:
    """
    fetches the full DOAJ dump (csv file) and returns it as a list of journals
    also checks the file for conformance to the expected format
    """
    errs = []
    l_journal: List[Journal] = []

    if not url:
        url = getSettingValue('doaj_dump_link')
    if not url:
        errs.append(_("URL für DOAJ-Dump nicht gesetzt."))
        return [],errs

    try:
        r = requests.get(url, allow_redirects=True)
    except Exception as e:
        errs.append(_(f"Fehler beim Holden des DOAJ-Dumps {e}"))
        return [],errs
    
    try:
        data = io.StringIO(r.content.decode('utf-8'),newline='')
        data.seek(0)

        reader = csv.DictReader(data, delimiter=',', quotechar='"')
        for row in reader:
            j = Journal()
            j.title = row.get('Journal title',None)
            j.url = row.get('URL in DOAJ',None)
            j.print_issn = row.get('Journal ISSN (print version)',None)
            j.e_issn = row.get('Journal EISSN (online version)',None)
            j.added_on_date = row.get('Added on Date',None)
            j.last_updated_date= row.get('Last updated Date',None)
            l_journal.append(j)
    except Exception as e:
        app.logger.error(f"exception={type(e).__name__}")
        app.logger.error(f"stacktrace={traceback.format_exc()}")
        errs.append(_(f"Fehler beim Parsen des DOAJ-Dumps."))
        errs.append(e)
        return [],errs
    
    return l_journal,[]


def _is_ipv4(ip: str) -> bool:
    """
    Cheap IPv4 check for a dotted-quad string (no network I/O, no extra deps).
    Returns True only for 4 dot-separated decimal octets 0-255, with no leading
    signs/whitespace. Used to filter IPv6 out of the GeoIP source CSV.
    """
    if not isinstance(ip, str):
        return False
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        if part != '0' and part.startswith('0'):
            # disallow leading zeros (e.g. "01") - not a canonical dotted quad
            return False
        if not (0 <= int(part) <= 255):
            return False
    return True


def getGeoIPFile(url=None, path=None) -> Tuple[str,List[str]]:
    """
    Obtains a GeoIP range file in the format `ip_from,ip_to,country_code` and
    writes it to a temporary CSV file, returning the path.

    Data source: DB-IP `dbip-country-lite` (CC-BY-4.0,
    https://db-ip.com), which provides `network_start_ip,network_end_ip,country_code,country_name`
    in dotted-quad form.

    - If `path` is given, it is treated as a local file (.csv or .csv.gz) and
      no download happens.
    - Otherwise the URL is resolved from the `geoip_link` setting, then `--url`
      override, then the bundled default (DEFAULT_GEOIP_URL).
    - The URL may contain `{YYYY}` and `{MM}` placeholders, substituted with the
      current year/month (the DB-IP source versions files by date).

    Transformations applied:
      1. gunzip when the source is gzip-compressed (by extension or magic bytes)
      2. parse as CSV
      3. keep only IPv4 rows (drop IPv6 - the geoip table uses INET4)
      4. drop the `country_name` column
      5. validate the 2-char country code

    Returns (path_to_temp_csv, errs). The temp file is deleted by the caller
    (expected in a `finally`).
    """
    errs: List[str] = []

    if not path:
        if not url:
            url = getSettingValue('geoip_link')
        if not url:
            url = DEFAULT_GEOIP_URL

        # substitute year/month placeholders ({YYYY}, {MM}) with the current date
        now = datetime.datetime.now()
        url = url.replace('{YYYY}', f"{now.year:04d}").replace('{MM}', f"{now.month:02d}")

        try:
            app.logger.info(f"downloading GeoIP data from {url}")
            r = requests.get(url, allow_redirects=True, timeout=120)
            r.raise_for_status()
        except Exception as e:
            errs.append(_(f"Fehler beim Holen der GeoIP-Daten von {url}."))
            errs.append(e)
            return None, errs

        compressed = url.endswith('.gz')
        content = r.content
    else:
        if not os.path.isfile(path):
            errs.append(_(f"Datei nicht gefunden: {path}"))
            return None, errs
        compressed = path.endswith('.gz')
        try:
            with open(path, 'rb') as f:
                content = f.read()
        except Exception as e:
            errs.append(_(f"Fehler beim Lesen der Datei {path}."))
            errs.append(e)
            return None, errs

    # fall back to sniffing gzip magic bytes if not indicated by the suffix
    if not compressed and len(content) >= 2 and content[0] == 0x1f and content[1] == 0x8b:
        compressed = True

    text = None
    try:
        if compressed:
            text = gzip.decompress(content).decode('utf-8')
        else:
            text = content.decode('utf-8')
    except Exception as e:
        errs.append(_("Fehler beim Dekomprimieren/Dekodieren der GeoIP-Daten."))
        errs.append(e)
        return None, errs

    tmp = None
    count = 0
    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.csv', prefix='geoip_')
        tmp = open(fd, 'w', encoding='utf-8', newline='')
        writer = csv.writer(tmp)
        reader = csv.reader(io.StringIO(text, newline=''))
        for row in reader:
            if not row:
                continue
            if len(row) < 3:
                continue
            ip_from = row[0].strip()
            ip_to = row[1].strip()
            country_code = row[2].strip()
            if not _is_ipv4(ip_from) or not _is_ipv4(ip_to):
                # IPv6 or malformed - skip (geoip table is IPv4 only)
                continue
            if not re.fullmatch(r'[A-Z]{2}', country_code):
                errs.append(_(f"Ungültiger Ländercode übersprungen: {country_code}"))
                continue
            writer.writerow([ip_from, ip_to, country_code])
            count += 1
        tmp.flush()
        tmp.close()
        tmp = None
    except Exception as e:
        app.logger.error(f"exception={type(e).__name__}")
        app.logger.error(f"stacktrace={traceback.format_exc()}")
        errs.append(_("Fehler beim Verarbeiten der GeoIP-Daten."))
        errs.append(e)
        if tmp is not None:
            tmp.close()
        return None, errs

    app.logger.info(f"wrote {count} IPv4 GeoIP ranges to {tmp_path}")
    return tmp_path, errs

