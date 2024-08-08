import hashlib
from io import StringIO
import os
from os.path import  abspath, basename, splitext
from _vars import _err_invalid_folder
from  JinjaTemplateProcessor import  JinjaTemplateProcessor
from jinja2 import meta
from snowflake.connector.util_text import split_statements     
from logging import getLogger
import re

logger = getLogger(__name__)

# a v script is a script that is versioned and is applied in order
# it can have a few different states
# not deployed, and will be deployed next time ( no result)
# deployable but conflicting... this is an issue at the target level... not the script level
# deployed with this exact checksum ( checksum match maybe name mismatch...)
# deployed with a different checksum ( name match but checksum mismatch)
# skipped or will be skipped deployment because there was a script with a higher version deployed already
#   is it worth it to check the file system date vs last deployed date? maybe check this property at the target level
_script_status_q_V= "SELECT SCRIPT, CHECKSUM , INSTALLED_ON \
                     FROM {database_name}.{schema_name}.{table_name} \
                     WHERE (SCRIPT = '{script}' or CHECKSUM = '{checksum}')"

# r script is a script that is repeatable and is applied in order
# it can have a few different states
# not deployed, and will be deployed next time
# deployed with this exact checksum
# deployed with a different checksum ( revision)
# previously deployed with this checksum but now has a different checksum (ie a regression)
_script_status_q_R_script_name= "SELECT SCRIPT, CHECKSUM , INSTALLED_ON, INSTALLED_BY  FROM {database_name}.{schema_name}.{table_name} \
                     WHERE   SCRIPT = '{script}' \
                     ORDER BY INSTALLED_ON DESC LIMIT 1"
_script_status_q_R_checksum = "SELECT SCRIPT, CHECKSUM , INSTALLED_ON, INSTALLED_BY  FROM {database_name}.{schema_name}.{table_name} \
                     WHERE CHECKSUM = '{checksum}' \
                     ORDER BY INSTALLED_ON DESC LIMIT 1"

# an a script is a script that is always applied and is applied in order  
# it can have similar states as a r script except they will always be deployed



class schemaChangeScript:
    def __init__(self, path, jinja_processor: JinjaTemplateProcessor):
        self.script_full_path = abspath(path)
        self.script_name = basename(path)
        (file_part, extension_part) = splitext(self.script_name)
        if extension_part.upper() == ".JINJA":
            self.script_name = file_part
        self.script_type = self.script_name[0]
        self.version = self.script_name[1:].split('__')[0]
        self.description = self.script_name.split('__')[1].capitalize()


        if not os.path.isfile(path):
            raise ValueError(_err_invalid_folder.format(folder_type='script_path', path=path))
        with open(path, 'r') as f:
            self.template = f.read()
        try:
            self.content = jinja_processor.render(self.template)  # config should be batteries included...s
            self.checksum = hashlib.sha224(self.content.encode('utf-8')).hexdigest()
            self.parse_errors = False
        except Exception as e:
            # Handle the exception here
            print(f"An error occurred: {e}")
            self.parse_errors = meta.find_undeclared_variables(self.content)
        
        self.touched_warehouse = False
        self.touched_role = False
        self.touched_database = False
        self.touched_schema = False
        self.statements = [schemaChangeScriptStatement(statement, is_put_or_get) for statement, is_put_or_get in split_statements(StringIO(self.content)) if statement.strip() != '']
        for statement in self.statements:
            if statement.indirect:
                if statement.indirect.group(1).upper() in ['ROLE']:
                    self.touched_role = True
                elif statement.indirect.group(1).upper() in ['WAREHOUSE']:
                    self.touched_warehouse = True
                elif statement.indirect.group(1).upper() in ['DATABASE']:
                    self.touched_database = True
                elif statement.indirect.group(1).upper() in ['SCHEMA']:
                    self.touched_schema = True
            elif statement.direct:
                if statement.direct.group(1).upper() in ['ROLE']:
                    self.touched_role = True
                elif statement.direct.group(1).upper() in ['WAREHOUSE']:
                    self.touched_warehouse = True
                elif statement.direct.group(1).upper() in ['DATABASE']:
                    self.touched_database = True
                elif statement.direct.group(1).upper() in ['SCHEMA']:
                    self.touched_schema = True


    def __str__(self):
            return self.checksum + '/n' +self.content 
    def deploy(self,session):
        session.script_cursor.execute("ALTER SESSION SET QUERY_TAG = '{query_tag}'".format(query_tag=session.conArgs["session_parameters"]["QUERY_TAG"] + self.script_name)) 
        for statement in self.statements: 
            session.script_cursor.execute(statement.sql, _is_put_get=statement.is_put_or_get )
        session.script_cursor.execute("ALTER SESSION SET QUERY_TAG = '{query_tag}'".format(query_tag=session.conArgs["session_parameters"]["QUERY_TAG"])) 
       
        if self.touched_role:
            session.script_cursor.execute("USE ROLE %s", (session.role))
        if self.touched_warehouse:
            session.script_cursor.execute("USE WAREHOUSE %s", (session.warehouse))
        if self.touched_database:
            session.script_cursor.execute("USE DATABASE %s", (session.database))
        if self.touched_schema:
            session.script_cursor.execute("USE SCHEMA %s", (session.schema))

    def get_status(self,session,version=None,checksum_installed_on=None, latest_installed_on=None):
        st = "SELECT DISTINCT SCRIPT, CHECKSUM , INSTALLED_ON  FROM {database_name}.{schema_name}.{table_name} WHERE SCRIPT_TYPE = 'R' AND  STATUS = 'Success' and SCRIPT = '{script}'"
        #session.logcursor.execute("select * from %s where script_name = %s and script_type = %s and version = %s", (session.change_history_table)))
    def render(self, path):
        with open(path + self.script_name, 'w') as f:
            f.write(self.content)

class schemaChangeScriptStatement():
    _re_direct_session_touch = r'USE\s+(ROLE|WAREHOUSE|DATABASE|SCHEMA|\w)\s+(\w+)' 
    _re_indirect_session_touch = r'CREATE\s+(OR\s+REPLACE\s+)?(TRANSIENT\s+)?(WAREHOUSE|DATABASE|SCHEMA)\s+(IF\s+NOT\s+EXISTS\s+)?(\w+)' 
    _re_DML_pattern = r'(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b'
    _re_DDL_pattern = r'(CREATE|ALTER|DROP|COMMENT)\b'
    _re_query_pattern = r'(SELECT|SHOW|DESCRIBE|EXPLAIN|CALL)\b'
    _re_permission_pattern = r'(GRANT|REVOKE)\b'
    _re_query_details_pattern = r"(WITH\s+\w+\s+AS\s+\(.*?\))?\s*(SELECT\s+.*?)(?:\s+FROM\s+.*?|\s+JOIN\s+.*?|\s+WHERE\s+.*?|\s+GROUP\s+BY\s+.*?|\s+HAVING\s+.*?|\s+ORDER\s+BY\s+.*?|\s+LIMIT\s+.*?|\s+OFFSET\s+.*?)?\s*;"

    def __init__(self, sql:str, is_put_or_get:bool):
        self.sql = sql
        self.is_put_or_get = is_put_or_get
        self.indirect = re.search(self._re_indirect_session_touch, sql, re.IGNORECASE)
        self.direct = re.search(self._re_direct_session_touch, sql, re.IGNORECASE)
        
    def __str__(self):
        return self.sql
    def __repr__(self):
        return self.sql
    def __eq__(self, other):
        return self.sql == other.sql
    def __hash__(self):
        return hash(self.sql)
    def __ne__(self, other):
        return not(self == other)
    def is_ddl(self):
        return bool(re.search(self._re_DDL_pattern, self.sql, re.IGNORECASE))
    def is_dml(self):
        return bool(re.search(self._re_DML_pattern, self.sql, re.IGNORECASE))
    def is_query(self):
        return bool(re.search(self._re_query_pattern, self.sql, re.IGNORECASE))
    def is_permission(self):
        return bool(re.search(self._re_permission_pattern, self.sql, re.IGNORECASE))
    