import json
import datetime
import mariadb
import re
import logging
import ipaddress
import hashlib
from uuid import uuid4
from typing import Optional
from yacryptopan import CryptoPAn

from flask import Flask, request, current_app
from flask.sessions import SessionInterface as FlaskSessionInterface
from flask.sessions import SessionMixin
from werkzeug.datastructures import CallbackDict
from flask_babel.speaklater import LazyString

from oajf.util import logfunc
from oajf.db import get_db

# LazyString not serializable...
class JSONEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, LazyString):
            return str(o)
        return super().default(o)

class ServerSideSession(CallbackDict, SessionMixin):

    def __init__(self, initial=None, sid=None, permanent=False):
        def on_update(self):
            self.modified = True
            self.accessed = True

        CallbackDict.__init__(self, initial, on_update)

        self.sid = sid
        if permanent:
            self.permanent = permanent
        self.modified = False
        self.accessed = False


class SessionData:
    id: int
    session_id: str
    ip_address: str
    ip_group: str
    country_code: str
    http_method: str
    request_path: str
    post_data: str
    form_data: str
    session_data: str
    user_agent: str
    last_activity: datetime.datetime
    expires: datetime.datetime

    def __init__(self):
        self.id = None
        self.country_code = None

class SessionInterface(FlaskSessionInterface):

    def _generate_sid(self):
        return str(uuid4())
    
class MariaDBSession(object):
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.session_interface = MariaDBSessionInterface(app)

class MariaDBSessionInterface(SessionInterface):
    session_class = ServerSideSession

    def __init__(self, app: Flask):
        self.app = app
        self.session_class.permanent = app.config.get('SESSION_PERMANENT',False)

        self.m_ip_group = {}
        d = app.config.get('IP_GROUPS',{})
        for k in d.keys():
            l = d[k]
            for x in l:
                if len(x) == 2: c = (ipaddress.IPv4Address(x[0]),ipaddress.IPv4Address(x[1]))
                elif len(x) == 1: c = (ipaddress.IPv4Address(x[0]),ipaddress.IPv4Address(x[0]))
                else: c = None
                if c: self.m_ip_group[c] = k

        self.crypto =  CryptoPAn(''.join([chr(x) for x in range(0, 32)]).encode())

    def getGroupForIP(self,ip) -> Optional[str]:
        l = []
        a = ipaddress.IPv4Address(ip)

        for k,v in self.m_ip_group.items():
            if a >= k[0] and a <= k[1]:
                if not v in l:
                    l.append(v)
        
        return '; '.join(l) if l else None

    #@logfunc
    def open_session(self, app, request):
        sd: SessionData = None

        sid = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
        if not sid:
            sid = self._generate_sid()
            return self.session_class(sid=sid, permanent=self.session_class.permanent)

        sd = self.readSessionData(sid)
        if sd is None:
            sid = self._generate_sid()
            return self.session_class(sid=sid, permanent=self.session_class.permanent)

        data = json.loads(sd.session_data)
        if data:
            return self.session_class(dict(data), sid=sid)
        return self.session_class(sid=sid, permanent=self.session_class.permanent)

    #@logfunc
    def save_session(self, app, session, response):
        sd: SessionData = None
        update_session_data = True
        store_request_data = app.config.get('STORE_REQUEST_DATA',False)

        for path in current_app.config.get('SESSION_IGNORE_PATHS',[]):
            if match := re.search(path,request.path,):
                update_session_data = False
                break
        
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)

        if not session:
            if session.modified:
                conn = get_db()
                cursor = conn.cursor(dictionary=True)
                cursor.execute('DELETE FROM session WHERE session_id = %s', (session.sid,))
                conn.commit()
                conn.close()

                response.delete_cookie(app.config["SESSION_COOKIE_NAME"], domain=domain, path=path)
            return

        conditional_cookie_kwargs = {}
        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        samesite = self.get_cookie_samesite(app)
        expires = self.get_expiration_time(app, session)
        last_activity = datetime.datetime.now(datetime.timezone.utc)
        post_data = request.data.decode('UTF-8') if store_request_data else None
        form_data = request.form if store_request_data else None
        data = dict(session)

#        if update_session_data and post_data:
#            for path,sub in current_app.config.get('MIN_FORM_POST_DATA_LENGTH',{}).items():
#                print ("path",path)
#                print ("request path",request.path)
#                if match := re.search(path,request.path):
#                    for k,l in sub.items():
#                        x = post_data.get(k,'')
#                        if x and len(x) < l:
#                            update_session_data = False
#                            break
#                        else:
#                            continue
#                    break
#
#        if update_session_data and form_data:
#            for path,sub in current_app.config.get('MIN_FORM_POST_DATA_LENGTH',{}).items():
#                print ("path",path)
#                print ("request path",request.path)
#                if match := re.search(path,request.path):
#                    for k,l in sub.items():
#                        x = form_data.get(k,'')
#                        if x and len(x) < l:
#                            update_session_data = False
#                            break
#                        else:
#                            continue
#                    break

        sd = self.readSessionData(session.sid)
        if sd is None:
            update_session_data = True
        
        if update_session_data:
            if sd is None:
                sd = SessionData()
                is_new = True
            else:
                is_new = False
            sd.session_id = session.sid
            sd.http_method = request.method
            sd.request_path = request.path
            sd.post_data = json.dumps(post_data)
            sd.form_data = json.dumps(form_data)
            sd.session_data = json.dumps(data,cls=JSONEncoder)
            sd.user_agent = str(request.user_agent)
            sd.expires = expires
            sd.last_activity = last_activity

            if is_new:
                sd.ip_address = request.remote_addr
                sd.country_code = self.getCountryCodeForIp(sd.ip_address)
                sd.ip_group = self.getGroupForIP(sd.ip_address)
                store_ip_mode = app.config.get('STORE_IPS','plain')

                if store_ip_mode == 'crytopan':
                    sd.ip_address = self.crypto.anonymize(sd.ip_address)
                elif store_ip_mode == 'sha256':
                    sd.ip_address = hashlib.sha256(uuid4().hex.encode('utf-8')+sd.ip_address.encode('utf-8')).hexdigest()
                else:
                    pass

            self.writeSessionData(sd)

        response.set_cookie(app.config["SESSION_COOKIE_NAME"], session.sid,
                            expires=expires, httponly=httponly,
                            domain=domain, path=path, secure=secure,
                            samesite=samesite, max_age = None,
                            **conditional_cookie_kwargs)
        

    #@logfunc
    def readSessionData(self,session_id:str) -> Optional[SessionData]:
        o:SessionData = None
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        try:
            l = []
            sql = "SELECT id,session_id,ip_address,ip_group,country_code,http_method,request_path,post_data,form_data,session_data,user_agent,last_activity,expires FROM session WHERE session_id=?"
            cur.execute(sql,(session_id,))
            row = cur.fetchone()

            if row:
                o = SessionData()
                for k,v in row.items():
                    setattr(o,k,v)

            return o
        except mariadb.Error as e:
            current_app.logger.error(type(e))
            current_app.logger.error(e)
            raise e
        except Exception as e:
            current_app.logger.error(type(e))
            current_app.logger.error(e)
            raise e
        finally:
            if conn:
                conn.close()

    #@logfunc
    def writeSessionData(self,o: SessionData):
        conn = get_db()
        cur = conn.cursor()
        try:
            if o.id is None: 
                sql = """
                INSERT INTO session
                (
                session_id,ip_address,ip_group,country_code,
                http_method,request_path,post_data,form_data,
                session_data,user_agent,last_activity,expires
                )
                VALUES
                (
                ?,?,?,?,
                ?,?,?,?,
                ?,?,?,?
                )
                """
                cur.execute(sql,
                    (o.session_id,
                    o.ip_address,
                    o.ip_group,
                    o.country_code,
                    o.http_method,
                    o.request_path,
                    o.post_data,
                    o.form_data,
                    o.session_data,
                    o.user_agent,
                    o.last_activity,
                    o.expires,
                    )
                )
                o.id = cur.lastrowid
            else:
                sql = """
                UPDATE session SET 
                session_id=?,ip_address=?,ip_group=?,country_code=?,http_method=?,request_path=?,post_data=?,
                form_data=?,session_data=?,user_agent=?,last_activity=?,expires=? 
                WHERE 
                session_id=?
                """
                cur.execute(sql,
                    (o.session_id,
                    o.ip_address,
                    o.ip_group,
                    o.country_code,
                    o.http_method,
                    o.request_path,
                    o.post_data,
                    o.form_data,
                    o.session_data,
                    o.user_agent,
                    o.last_activity,
                    o.expires,
                    o.session_id,
                    )
                )
            conn.commit()

        except mariadb.Error as e:
            current_app.logger.error(type(e))
            current_app.logger.error(e)
            if conn:
                conn.rollback()
            raise e
        except Exception as e:
            current_app.logger.error(type(e))
            current_app.logger.error(e)
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()


    #@logfunc
    def getCountryCodeForIp(self,ip:str) -> Optional[str]:
        country_code:str = None
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        try:
            l = []
            sql = "SELECT country_code FROM geoip WHERE ? >= ip_from and ? <= ip_to"
            cur.execute(sql,(ip,ip,))
            row = cur.fetchone()

            if row:
                for v in row.values():
                    country_code = v
            return country_code
        except mariadb.Error as e:
            current_app.logger.error(type(e))
            current_app.logger.error(e)
            raise e
        except Exception as e:
            current_app.logger.error(type(e))
            current_app.logger.error(e)
            raise e
        finally:
            if conn:
                conn.close()
