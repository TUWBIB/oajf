import datetime
import traceback
import json
from typing import List,Dict

from flask import Flask,g
from flask.cli import AppGroup
import click

from oajf.models import Publisher,Journal,Setting
from oajf.db import get_db,init as db_init
from oajf.db import (
    saveJournal as db_saveJournal,
    deleteJournal as db_deleteJournal,
    readJournals as db_readJournals,
    readPublishers as db_readPublishers,
    savePublisher as db_savePublisher,
    deletePublisher as db_deletePublisher,
    readExcelFiles as db_readExcelFiles,
    saveExcelFile as db_saveExcelFile,
    deleteExcelFile as db_deleteExcelFile,
    readSettings as db_readSettings,
    deleteSetting as db_deleteSetting,
    saveSetting as db_saveSetting
)
from oajf.util import get_publishers,get_settings,getDOAJChangesFileAsExcelWorkbook,getDOAJDump

def register_cli(app: Flask):
    oajf_cli = AppGroup('oajf')
    app.cli.add_command(oajf_cli)


    @app.cli.command(short_help="Read from an utf-8 encoded .sql file and execute every command separated by a semicolon on the database.")
    @click.argument('path')
    def db_execute_script(path: str):

        """
        Read from an utf-8 encoded .sql file and execute every command separated by a semicolon on the database.
        """
        db = db_init(app)

        conn = get_db()
        cur = conn.cursor()
        with app.open_resource(path) as f:
            commands = []
            command = ""
            for row in f.read().decode("utf8").split("\n"):
                if row != '':
                    row = row.strip()
                    command += " " + row
                    if row.endswith(";"):
                        commands.append(command.lstrip())
                        command = ""
            try:
                for c in commands:
                    affected_rows = cur.execute(c)
                    print(f("{affected_rows} affected by {c}"))
                conn.commit()
                print("script completed successfully")
            except:
                conn.rollback()
                print("script failed")
            finally:
                conn.close()

    @app.cli.command()
    def db_init_command():
        db_execute_script("schema.sql")


    @oajf_cli.command(short_help="Export current settings as json.")
    @click.argument('file')
    def exportSettings(file: str):
        """
        Export current settings as json.
        """
        db = db_init(app)

        l_setting: List[Setting] = db_readSettings()
        d: Dict[str,Dict[str,str]] = {}

        for x in l_setting:
            e = d.setdefault(x.name,{})
            e['value'] = x.value
            e['value_en'] = x.value_en
            e['value_de'] = x.value_de

        with open(file,'w') as f:
            json.dump(d,f,indent=4)

    @oajf_cli.command(short_help="Deletes current settings and imports new settings from a json file. Use with care.")
    @click.argument('file')
    def importSettings(file: str):
        """
        Deletes current settings and reimports from a json file.
        """
        db = db_init(app)

        l_setting: List[Setting]
        l_new: List[Setting] = []
        o: Setting

        with open(file,'r') as f:
            data = json.load(f)

        for k,d in data.items():
            o = Setting()
            o.name = k
            o.value = d.get('value',None)
            o.value_en = d.get('value_en',None)
            o.value_de = d.get('value_de',None)
            l_new.append(o)

        try:
            conn = get_db()
            l_setting = db_readSettings(transaction_conn=conn)
            for o in l_setting:
                db_deleteSetting(o,transaction_conn=conn)
            for o in l_new:
                db_saveSetting(o,transaction_conn=conn)
            conn.commit()

        except Exception as e:
            if conn is not None:
                conn.rollback()
            print(e)
            print(traceback.format_exc())
        finally:
            if conn is not None:
                conn.close()

        get_settings(force_reload=True)

    @oajf_cli.command(short_help="Renews geoip info.")
    @click.argument('file')
    def importGeoIP(file: str):
        """
        Import geoip-file.
        """
        db = db_init(app)

        try:
            conn = get_db()
            cur = conn.cursor()
            sql = "DELETE FROM `geoip`;"
            cur.execute(sql)
            sql = f"LOAD DATA LOCAL INFILE '{file}' INTO TABLE `geoip` FIELDS TERMINATED BY ',' (ip_from,ip_to,country_code);"
            cur.execute(sql)
            conn.commit()
        except Exception as e:
            if conn is not None:
                conn.rollback()
            print(e)
            print(traceback.format_exc())
        finally:
            if conn is not None:
                conn.close()


    @oajf_cli.command(short_help="Imports publishers from json files.")
    @click.argument('file')
    def importPublishers(file: str):
        """
        Import publishers.
        """

        if not click.confirm(f'Import publishers from json file? This deletes all existing publishers including journals and uploaded excel-files. Are you sure'):
            exit(0)

        l_publisher: List[Publisher]
        l_new: List[Publisher] = []
        o: Publisher

        with open(file,'r') as f:
            data = json.load(f)

        for i in data:
            o = Publisher.fromDict(i)
            l_new.append(o)

        try:
            conn = get_db()
            l_publisher,_ = db_readPublishers(transaction_conn=conn)
            for o in l_publisher:
                db_deleteJournal(None,transaction_conn=conn,publisher_id=o.id)
                db_deleteExcelFile(None,transaction_conn=conn,publisher_id=o.id)
                db_deletePublisher(o,transaction_conn=conn)
            for o in l_new:
                db_savePublisher(o,transaction_conn=conn)
            conn.commit()

        except Exception as e:
            if conn is not None:
                conn.rollback()
            print(e)
            print(traceback.format_exc())
        finally:
            if conn is not None:
                conn.close()

        get_settings(force_reload=True)



    # obsolete
    #
    # commandline-usage
    # flask db fetch_doaj_file --ignore-doaj-linking 0
    # or
    # flask db fetch_doaj_file --ignore-doaj-linking 1
    #
    # use --url param to explicitly set the download location, e.g. a file saved in the static dir
    @app.cli.command()
    @click.option('--ignore-doaj-linking',default = 0)
    @click.option('--url',default = None)
    def fetch_doaj_file(ignore_doaj_linking,url):
        """ Download of DOAJ-changes-file """
        db = db_init(app)

        conn = None
        title = None
        issn = None
        reason = None
        date = None

        map_issn: Dict[str,List[str]] = {}
        l_journal: List[Journal] = []
        j: Journal

        wb,data,errs = getDOAJChangesFileAsExcelWorkbook(url)
        if errs:
            s = '; '.join(errs)
            print(f"Errors occured during fetching of DOAJ-changes-file {s}")
            exit(1)

        try:
            sheet = wb['Withdrawn']
            for i,row in enumerate(sheet.rows):
                if i < 6:
                    continue

                title = row[0].value
                if title: title = title.strip()
                issn = row[1].value
                if issn: issn = issn.strip()
                date = row[2].value
                reason = row[3].value
                if reason: reason = reason.strip()

                if issn is not None and issn != 'None':
                    map_issn[issn] = [title,date,reason]

            get_publishers()
            conn = get_db()

            for k,v in map_issn.items():
                for j in db_readJournals(e_issn=k,only_active=True,publisher_shallow=True):
                    j.publisher = g.m_publishers[j.publisher.id]
                    j.withdraw_reason = map_issn[k][2]
                    j.withdraw_date = map_issn[k][1]
                    if j.publisher.is_doaj == 1 or j.publisher.doaj_linked == 1:
                        j.to_be_deleted = 1
                    else:
                        j.to_be_deleted = 0

                    l_journal.append(j)

            print(f"{len(l_journal)} journals found which are withdrawn by DOAJ")
            for j in l_journal:
                print (f"{j.id}: {j.e_issn} - {j.title} ({j.publisher.id},{j.publisher.name}), withdrawn due to {j.withdraw_reason} on {j.withdraw_date}")

            l_ignored = []
            l_deleted = []

            for j in l_journal:
                if j.publisher.is_doaj == 1 or \
                    ignore_doaj_linking == 1 or \
                    (j.publisher.doaj_linked == 1 and ignore_doaj_linking == 0):
                        l_deleted.append(j)
                else:
                    l_ignored.append(j)

            print(f"{len(l_ignored)} journals ignored due to doaj-linking-options")
            for j in l_ignored:
                print (f"{j.id}: {j.e_issn} - {j.title} ({j.publisher.id},{j.publisher.name}), withdrawn due to {j.withdraw_reason} on {j.withdraw_date}")

            print(f"{len(l_deleted)} journals to be deleted")
            for j in l_deleted:
                print (f"{j.id}: {j.e_issn} - {j.title} ({j.publisher.id},{j.publisher.name}), withdrawn due to {j.withdraw_reason} on {j.withdraw_date}")

            if len(l_deleted) > 0:
                if click.confirm('Delete the listed journals?'):
                    for j in l_deleted:
                        db_deleteJournal(None,transaction_conn=conn,id=j.id)
                        print(f"deleted journal {j.id}")
                    conn.commit()
                else:
                    print ("Sissy!")

        except Exception as e:
            if conn is not None:
                conn.rollback()
            print(e)
            print(traceback.format_exc())
        finally:
            if conn is not None:
                conn.close()


    # obsolete
    #
    # DOAJ full dump import/update
    # structure of csv-file:
    # Journal title,Journal URL,URL in DOAJ,When did the journal start to publish all content using an open license?,Alternative title,Journal ISSN (print version),Journal EISSN (online version),Keywords,Languages in which the journal accepts manuscripts,Publisher,Country of publisher,Other organisation,Country of other organisation,Journal license,License attributes,URL for license terms,Machine-readable CC licensing information embedded or displayed in articles,URL to an example page with embedded licensing information,Author holds copyright without restrictions,Copyright information URL,Review process,Review process information URL,Journal plagiarism screening policy,Plagiarism information URL,URL for journal's aims & scope,URL for the Editorial Board page,URL for journal's instructions for authors,Average number of weeks between article submission and publication,APC,APC information URL,APC amount,Journal waiver policy (for developing country authors etc),Waiver policy information URL,Has other fees,Other fees information URL,Preservation Services,Preservation Service: national library,Preservation information URL,Deposit policy directory,URL for deposit policy,Persistent article identifiers,Article metadata includes ORCIDs,Journal complies with I4OC standards for open citations,Does the journal comply to DOAJ's definition of open access?,URL for journal's Open Access statement,Continues,Continued By,LCC Codes,Subjects,DOAJ Seal,Added on Date,Last updated Date,Number of Article Records,Most Recent Article Added
    #
    # commandline-usage
    # flask db doaj_import_dump  --ignore-doaj-linking 0
    # flask db doaj_import_dump  --ignore-doaj-linking 0 --url "http://127.0.0.1:5001/static/journalcsv__doaj_20250228_1220_utf8.csv"
    @app.cli.command()
    @click.option('--ignore-doaj-linking',default = 0)
    @click.option('--url',default = None)
    def doaj_import_dump(ignore_doaj_linking,url):
        db = db_init(app)

        j: Journal = None
        p: Publisher
        l_journal_csv: List[Journal] = []
        l_journal_db: List[Journal]
        l_updated: List[Journal] = []
        l_new: List[Journal] = []
        m_eissn: Dict[str,Journal] = {}
        m_pissn: Dict[str,Journal] = {}

        publishers = get_publishers()
        publishers[:] = [p for p in publishers if p.is_doaj == 1]
        p = publishers[0]
        l_journal_db = db_readJournals(publisher=p,publisher_shallow=True)
        print (f"number of journals found in database: {len(l_journal_db)}")

        for j in l_journal_db:
            if j.e_issn:
                if j.e_issn in m_eissn:
                    print(f"WARNING: e_issn found multiple times for journals in database: {j.e_issn}")
                else:
                    m_eissn[j.e_issn] = j

            if j.print_issn:
                if j.print_issn in m_pissn:
                    print(f"WARNING: print_issn found multiple times for journals in database: {j.print_issn}")
                else:
                    m_pissn[j.print_issn] = j

        l_journal_csv,errs = getDOAJDump(url)
        for j in l_journal_csv:
            e_issn_found = False
            print_issn_found = False
            if j.e_issn:
                if j.e_issn in m_eissn:
                    e_issn_found = True
                else:
                    pass
    #                   print(f"journal e_issn not found : {j.title}, {j.e_issn}, {j.added_on_date}, {j.last_updated_date}")

            if j.print_issn:
                if j.print_issn in m_pissn:
                    print_issn_found = True
                else:
                    pass
    #                    print(f"journal print_issn not found : {j.title}, {j.print_issn}, {j.added_on_date}, {j.last_updated_date}")

            if e_issn_found:
                j_db = m_eissn[j.e_issn]
                diffs = j.getDifferences(j_db)
                if diffs:
                    j.id = j_db.id
                    j.valid_till = j_db.valid_till
                    j.diffs = diffs
                    l_updated.append(j)
                    print(f"journal updated (e-issn matched): title:{j.title}, e-issn:{j.e_issn}, p-issn:{j.print_issn} - new/old:{j.diffs}")
            elif print_issn_found:
                j_db = m_pissn[j.print_issn]
                diffs = j.getDifferences(j_db)
                if diffs:
                    j.id = j_db.id
                    j.valid_till = j_db.valid_till
                    j.diffs = diffs
                    l_updated.append(j)
                    print(f"journal updated (p-issn matched): title:{j.title}, e-issn:{j.e_issn}, p-issn:{j.print_issn} - new/old:{j.diffs}")
            else:
                j.id = -1
                j.publisher = p
                j.valid_till = datetime.datetime.today()
                j.valid_till = j.valid_till.replace(month=12,day=31,hour=23,minute=59,second=59)
                l_new.append(j)


        if len(l_updated)>0:
            if click.confirm(f'Update {len(l_updated)} changed journals?'):
                for j in l_updated:
                    db_saveJournal(j)
                    print(f"journal updated: id:{j.id}, title:{j.title}, e-issn:{j.e_issn}, p-issn:{j.print_issn}")
            else:
                print ("Sissy!")

        if len(l_new)>0:
            if click.confirm(f'Insert {len(l_new)} new journals?'):
                for j in l_new:
                    j = db_saveJournal(j)
                    print(f"journal added: id: {j.id}, title:  {j.title}, e-issn:{j.e_issn}, p-issn:{j.print_issn}")
            else:
                print ("Sissy!")
