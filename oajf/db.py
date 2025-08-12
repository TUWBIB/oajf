from __future__ import annotations

import logging
import traceback
from threading import Lock
from functools import wraps
from typing import List,Dict,Tuple

try:
    import mariadb
except:
    pass

from flask import g,current_app
from oajf.models import Journal,Publisher,Link,Excel,Setting,OASTATUS, APPLICATION_REQUIREMENT,LINKTYPE

database = None

def init(app):
    global database

    if database is None:
        with app.app_context():
            db_config = current_app.config['DATABASE']
            database = DB(
                host = db_config['host'],
                port = db_config['port'],
                db = db_config['database'],
                user = db_config['user'],
                passwd = db_config['password'],
                poolsize = db_config['poolsize'],
                autocommit = db_config['autocommit'],
                app = app,
            )
            database.connect()

    return database


def get_db():
    conn = database.getConnection()
    return conn

def getPoolStats():
    has_pool:bool = database.pool is not None
    free:int = 0
    used:int = 0
    

    if database and database.pool:
        free, used = len(database.pool._connections_free), len(database.pool._connections_used)

    return free, used, has_pool


def ensurePublishersLoaded(force_reload=False):
    l_publisher = getattr(g, 'publishers', None)
    if l_publisher is None or force_reload:
        l_publisher, m_publisher = readPublishers()

        g.publishers = l_publisher
        g.m_publishers = m_publisher
    
    l_publisher

def saveJournal(o:Journal,transaction_conn=None,) -> Journal:
    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()
        sql_update = """
            UPDATE journal 
            SET title=?,link=?,print_issn=?,e_issn=?,valid_till=?
            WHERE id=?
        """
        sql_insert = """
            INSERT INTO journal
            (title,link,print_issn,e_issn,valid_till,publisher_id)
            VALUES (?,?,?,?,?,?)
        """

        if o.id is None or int(o.id) == -1:
            cur.execute(sql_insert,
                        (o.title,
                        o.url,
                        o.print_issn,
                        o.e_issn,
                        o.valid_till,
                        o.publisher.id,
                        ))
            o.id = cur.lastrowid
        else:
            cur.execute(sql_update,
                        (o.title,
                        o.url,
                        o.print_issn,
                        o.e_issn,
                        o.valid_till,
                        o.id,
                        ))
        if not transaction_conn:
            conn.commit()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return o

def deleteJournal(o:Journal,transaction_conn=None,id=None, e_issn=None,publisher_id=None ) -> int:
    rows_affected = 0
    params = []

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()
        sql = "DELETE FROM journal WHERE 1 = 1 "
        if o: 
            sql += "AND id=? "
            params.append(o.id)
        elif id: 
            sql += "AND id=? "
            params.append(id)
        elif e_issn: 
            sql += "AND e_issn=? " 
            params.append(e_issn)
        elif publisher_id: 
            sql += "AND publisher_id=? " 
            params.append(publisher_id)

        if params:
            cur.execute(sql,params)
            rows_affected = cur.rowcount
            print(f"rows_affected {cur.rowcount}")

            if not transaction_conn:
                conn.commit()
    except Exception as e:
        if params:
            if not transaction_conn and conn:
                conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return rows_affected

def readJournals(
                transaction_conn=None,
                keyword: str = None, 
                 only_active: bool = True, 
                 publisher: Publisher = None,
                 order_sql: str = None,
                 limit_sql: str = None,
                 as_json: bool = False,
                 publisher_shallow: bool = False,
                 e_issn: str = None,
                 id: int = None,
                 order: str = None,
                 limit: int = None,
                 ) -> List[Journal]:
    l_journal: List[Journal] = []

    try:

        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        if keyword:
            keyword = keyword.strip()
            kw1 = kw2 = keyword
            expr = "%" + keyword + "%"
            kw1 = kw1.replace(' &',' and')
            kw1 = "%" + kw1 + "%"
            kw2 = kw2.replace(' and',' &')
            kw2 = "%" + kw2 + "%"


        sql = "SELECT j.id, j.title, j.link, j.print_issn, j.e_issn, j.valid_till, j. publisher_id "
        sql += "FROM journal j LEFT JOIN publisher p ON j.publisher_id=p.id "
        sql += "WHERE 1=1 "
        if only_active:
            sql += "AND j.valid_till >= CURDATE() "
        if keyword:
            sql += "AND (j.title LIKE ? OR j.title LIKE ? OR j.title LIKE ? OR j.print_issn LIKE ? OR j.e_issn LIKE ? OR p.name LIKE ?) "
        if publisher:
            sql += "AND p.id = "+str(publisher.id) + " "
        if e_issn:
            sql += "AND j.e_issn = '" + e_issn + "' "
        if id:
            sql += "AND j.id = " + str(id) + " "
        if order_sql:
            sql += order_sql
        if limit_sql:
            sql += limit_sql
        
        if order and not order_sql:
            s = ""
            a = order.split(",")
            for i,b in enumerate(a):
                if i>0: s += ","
                field,dir = b.split(".")
                if field == 'title': field = "j.title"
                if field == 'publisher': field = "p.name"
                if field == 'e_issn': field = "j.e_issn"
                if field == 'p_issn': field = "j.print_issn"
                if field == 'application_requirement': field = "p.application_requirement"
                if field == 'oa_status': field = "p.oa_status"
                if field == 'publisher_name': field = "p.name"
                s += field + " " + dir
            sql += ' ORDER BY ' + s

        if limit and not limit_sql:
            sql += ' LIMIT ' + str(limit)

        if keyword:
            cur.execute(sql,(expr,kw1,kw2,expr,expr,expr,))
        else:
            cur.execute(sql)

        for row in cur:
            j = Journal()
            j.id = row[0]
            j.title = row[1]
            j.url = row[2]
            j.print_issn = row[3]
            j.e_issn = row[4]
            j.valid_till = row[5]
            j.publisher = g.m_publishers[row[6]]
            if publisher_shallow:
                publisher_shallow = Publisher()
                publisher_shallow.id =j.publisher.id
                publisher_shallow.name = j.publisher.name
                j.publisher = publisher_shallow

            if as_json:
                l_journal.append(j.toDict())
            else:
                l_journal.append(j)
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()
    
    return l_journal

def saveLink(o:Link,transaction_conn=None,) -> Link:
    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        sql = """
            INSERT INTO link
            (publisher_id,link,linktype,linktext_de,linktext_en)
            VALUES 
            (?,?,?,?,?)
            """                  
        cur.execute(sql,
                    (o.publisher.id,
                    o.link,
                    o.linktype.key,
                    o.linktext_de,
                    o.linktext_en))
        o.id = cur.lastrowid

        if not transaction_conn:
            conn.commit()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return o


def savePublisher(o:Publisher,transaction_conn=None,) -> Publisher:
    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        sql_update = """
            UPDATE publisher
            SET name=?,validity=?,oa_status=?,application_requirement=?,
            funder_info=?,cost_coverage=?,valid_tu=?,article_type=?,further_info=?,
            funder_info_en=?,cost_coverage_en=?,valid_tu_en=?,article_type_en=?,further_info_en=?,
            is_doaj=?,doaj_linked=?
            WHERE id=?
        """
        sql_insert = """
            INSERT INTO publisher
            (name,validity,oa_status,application_requirement,
            funder_info,cost_coverage,valid_tu,article_type,further_info,
            funder_info_en,cost_coverage_en,valid_tu_en,article_type_en,further_info_en,
            is_doaj,doaj_linked
            )
            VALUES (?,?,?,?,
            ?,?,?,?,?,
            ?,?,?,?,?,
            ?,?
            )
            """                  

        if o.id is None or int(o.id) == -1:
            cur.execute(sql_insert,
                        (o.name,
                        o.validity,
                        o.oa_status.key,
                        o.application_requirement.key,
                        o.funder_info,
                        o.cost_coverage,
                        o.valid_tu,
                        o.article_type,
                        o.further_info, 
                        o.funder_info_en,
                        o.cost_coverage_en,
                        o.valid_tu_en,
                        o.article_type_en,
                        o.further_info_en, 
                        o.is_doaj,
                        o.doaj_linked,
                        ))
            o.id = cur.lastrowid
        else:
            cur.execute(sql_update,
                        (o.name,
                        o.validity,
                        o.oa_status.key,
                        o.application_requirement.key,
                        o.funder_info,
                        o.cost_coverage,
                        o.valid_tu,
                        o.article_type,
                        o.further_info, 
                        o.funder_info_en,
                        o.cost_coverage_en,
                        o.valid_tu_en,
                        o.article_type_en,
                        o.further_info_en,
                        o.is_doaj,
                        o.doaj_linked,
                        o.id,
                        ))
            deleteLink(None,transaction_conn=conn,publisher_id=o.id)
            
        for link in o.links:
            link.publisher = o
            link = saveLink(link,transaction_conn=conn)

        if not transaction_conn:
            conn.commit()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return o

def readPublishers(transaction_conn=None) -> Tuple[List[Publisher],Dict[int,Publisher]]:
    l_publisher: List[Publisher] = []
    m_publisher: Dict[int,Publisher] = {}
    sql_publisher = """
        SELECT 
        id,name,validity,oa_status,application_requirement,
        funder_info,cost_coverage,valid_tu,article_type,further_info,
        funder_info_en,cost_coverage_en,valid_tu_en,article_type_en,further_info_en,
        is_doaj,doaj_linked
        FROM publisher
    """
    sql_link = """
        SELECT 
        id,publisher_id,link,linktype,linktext_de,linktext_en
        FROM link
    """

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        cur.execute(sql_publisher)
        for row in cur:
            it = iter(range(0,30))     
            p = Publisher()
            p.id = row[next(it)]
            p.name = row[next(it)]
            p.validity = row[next(it)]
            p.oa_status = OASTATUS.get(row[next(it)],None)
            p.application_requirement = APPLICATION_REQUIREMENT.get(row[next(it)],None)
            p.funder_info = row[next(it)]
            p.cost_coverage = row[next(it)]
            p.valid_tu = row[next(it)]
            p.article_type = row[next(it)]
            p.further_info = row[next(it)]
            p.funder_info_en = row[next(it)]
            p.cost_coverage_en = row[next(it)]
            p.valid_tu_en = row[next(it)]
            p.article_type_en = row[next(it)]
            p.further_info_en = row[next(it)]
            p.is_doaj = row[next(it)]
            p.doaj_linked = row[next(it)]
            p.links = []
            l_publisher.append(p)
            m_publisher[p.id] = p

        cur.execute(sql_link)
        for row in cur:
            it = iter(range(0,30))     
            l = Link()
            l.id = row[next(it)]

            l.publisher = m_publisher[row[next(it)]]
            l.link = row[next(it)]
            l.linktype = LINKTYPE.get(row[next(it)],None)
            l.linktext_de = row[next(it)]
            l.linktext_en = row[next(it)]
            l.publisher.links.append(l)

        l_publisher.sort()
        for p in l_publisher:
            p.links.sort()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()
    
    return l_publisher,m_publisher


def deleteLink(o:Link,transaction_conn=None,publisher_id=None ) -> int:
    rows_affected = 0
    params = []

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        sql = "DELETE FROM link WHERE 1 = 1 "
        if o: 
            sql += "AND id=? "
            params.append(o.id)
        elif publisher_id: 
            sql += "AND publisher_id=? " 
            params.append(publisher_id)

        if params:
            cur.execute(sql,params)
            rows_affected = cur.rowcount

            if not transaction_conn:
                conn.commit()
    except Exception as e:
        if params:
            if not transaction_conn and conn:
                conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return rows_affected


def deletePublisher(o:Publisher,transaction_conn=None,id=None ) -> int:
    rows_affected = 0

    try:
        conn = transaction_conn if transaction_conn else get_db()

        if o:
            deleteLink(None,transaction_conn=conn,publisher_id=o.id)
        elif id:
            deleteLink(None,transaction_conn=conn,publisher_id=id)                       

        cur = conn.cursor()
        sql = "DELETE FROM publisher WHERE 1 = 1 "
        params = []
        if o: 
            sql += "AND id=? "
            params.append(o.id)
        elif id: 
            sql += "AND id=? " 
            params.append(id)

        if params:
            cur.execute(sql,params)
            rows_affected = cur.rowcount

            if not transaction_conn:
                conn.commit()
    except Exception as e:
        if params:
            if not transaction_conn and conn:
                conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return rows_affected


def readExcelFiles(transaction_conn=None,id=None, include_data=False) -> List[Excel]:
    e: Excel
    l_excel: List[Excel] = []

    sql = "SELECT id,name,uploaded,valid,publisher_id"
    if include_data:
        sql += ",file"
    sql += " FROM excelfilehistory"
    if id:
        sql += " WHERE id="+id

    try:
        ensurePublishersLoaded()
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        cur.execute(sql)
        for row in cur:
            it = iter(range(0,30))     
            e = Excel()
            e.id = row[next(it)]
            e.name = row[next(it)]
            e.uploaded = row[next(it)]
            e.valid = row[next(it)]
            e.publisher = g.m_publishers[row[next(it)]]
            if include_data:
                e.file = row[next(it)]
            l_excel.append(e)

        l_excel.sort()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return l_excel

def saveExcelFile(o:Excel,transaction_conn=None,) -> Journal:
    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()
        sql_update = """
            UPDATE excelfilehistory 
            SET name=?,file=?,valid=?,publisher_id=?
            WHERE id=?
        """
        sql_insert = """
            INSERT INTO excelfilehistory (name,file,valid,publisher_id)
            VALUES (?,?,?,?)
        """

        if o.id is None or int(o.id) == -1:
            cur.execute(sql_insert,
                        (o.name,
                        o.file,
                        o.valid,
                        o.publisher.id,
                        ))
            o.id = cur.lastrowid
        else:
            cur.execute(sql_update,
                        (o.name,
                        o.file,
                        o.valid,
                        o.publisher.id,
                        o.id,
                        ))
        if not transaction_conn:
            conn.commit()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return o


def deleteExcelFile(o:Excel,transaction_conn=None,id=None,publisher_id=None ) -> int:
    rows_affected = 0
    params = []

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()
        sql = "DELETE FROM excelfilehistory WHERE 1 = 1 "
        if o: 
            sql += "AND id=? "
            params.append(o.id)
        elif id: 
            sql += "AND id=? "
            params.append(id)
        elif publisher_id: 
            sql += "AND publisher_id=? " 
            params.append(publisher_id)

        if params:
            cur.execute(sql,params)
            rows_affected = cur.rowcount

            if not transaction_conn:
                conn.commit()
    except Exception as e:
        if params:
            if not transaction_conn and conn:
                conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return rows_affected

#
# settings
#
def readSettings(transaction_conn=None) -> List[Setting]:
    o: Setting
    l_setting: List[Setting] = []

    sql = """
        SELECT 
        id,name,value,value_en,value_de
        FROM setting
    """

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql)
        rows = cur.fetchall()
        for row in rows:
            o = Setting()
            o.id = row['id']
            o.name = row['name']
            o.value = row['value']
            o.value_en = row['value_en']
            o.value_de = row['value_de']
            l_setting.append(o)
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()
    
    return l_setting

def saveSetting(o:Setting,transaction_conn=None,) -> Setting:
    sql_update = """
        UPDATE setting
        SET name=?,value=?,value_en=?,value_de=?
        WHERE id=?
    """
    sql_insert = """
        INSERT INTO setting
        (name,value,value_en,value_de)
        VALUES (?,?,?,?)
        """                  
    params = []

    is_insert: bool = o.id is None or int(o.id) == -1
    sql = sql_insert if is_insert else sql_update

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()

        params.append(o.name)
        params.append(o.value)
        params.append(o.value_en)
        params.append(o.value_de)
        if not is_insert: params.append(o.id)
        cur.execute(sql,params)
        if is_insert: o.id = cur.lastrowid

        if not transaction_conn:
            conn.commit()
    except Exception as e:
        if not transaction_conn and conn:
            conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return o


def deleteSetting(o:Setting,transaction_conn=None,id=None ) -> int:
    rows_affected = 0

    try:
        conn = transaction_conn if transaction_conn else get_db()
        cur = conn.cursor()
        sql = "DELETE FROM setting WHERE 1 = 1 "
        params = []
        if o: 
            sql += "AND id=? "
            params.append(o.id)
        elif id: 
            sql += "AND id=? " 
            params.append(id)

        if params:
            cur.execute(sql,params)
            rows_affected = cur.rowcount

            if not transaction_conn:
                conn.commit()
    except Exception as e:
        if params:
            if not transaction_conn and conn:
                conn.rollback()
        current_app.logger.error(f"exception={type(e).__name__}")
        current_app.logger.error(f"stacktrace={traceback.format_exc()}")
        raise e
    finally:
        if not transaction_conn and conn:
            conn.close()

    return rows_affected


class DB():
    def __init__(self,host,db,user,passwd,port,poolsize=30,app=None,autocommit=True):
        self.host = host
        self.db = db
        self.user = user
        self.passwd = passwd
        self.port = port
        self.poolsize = poolsize
        self.autocommit = autocommit
        self.app = app 
        self.pool = None
        self.lock = Lock()


    def connect(self):
        if self.poolsize > 0:
            with self.lock:
                current_app.logger.info("database connect")
                self.pool = mariadb.ConnectionPool(
                    pool_name="oajf",
                    pool_size=int(self.poolsize),
                    pool_reset_connection=True,
                    host=self.host,
                    port=int(self.port),
                    user=self.user,
                    passwd=self.passwd,
                    db=self.db,
                    autocommit=self.autocommit,
                )

    def disconnect(self,signalnum=None,frame=None):
        if self.poolsize > 0:
            with self.lock:
                with self.app.app_context():
                    self.app.logger.info(f"database disconnect signalnum:{signalnum} frame:{frame}")
                    if self.pool:
                        self.pool.close()
                        self.pool = None
                    if signalnum and self.signalhandler:
                        self.signalhandler(signalnum,frame)

    # get connection
    # if pool active, get a connection from pool and check if it still works
    # otherwise just get a connection from database
    def getConnection(self,retrycount=0) -> mariadb.Connection:
        conn = None
        if self.poolsize > 0:
            with self.lock:
                if retrycount > self.pool.connection_count:
                    current_app.logger.fatal('cannot get database connection')
                    raise Exception("really can't get connection")

                conn:mariadb.Connection = None
                
                # connection available?
                try:
                    conn = self.pool.get_connection()
                except Exception as e:
                    current_app.logger.fatal('connection pool exhausted')
                    current_app.logger.fatal(e)
                    current_app.logger.fatal(traceback.format_exc())
                    raise e

                # check if connection works?
                try:
                    cur = conn.cursor()
                    cur.execute("SET NAMES utf8mb4")
                except Exception as e:
                    current_app.logger.warning('connection might have died, trying to replace in pool')
                    current_app.logger.warning(e)
                    current_app.logger.warning(traceback.format_exc())

                    conn.close()
                    self.pool._replace_connection(conn)

                    retrycount +=1
                    conn = self.getConnection(retrycount=retrycount)
                
                return conn   
        else:
            conn = mariadb.connect(
                host=self.host,
                port=int(self.port),
                user=self.user,
                passwd=self.passwd,
                db=self.db,
                autocommit=self.autocommit,
            )

            return conn


