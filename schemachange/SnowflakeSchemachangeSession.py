import snowflake.connector
import requests
import json
import warnings
import os
import time 
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from pandas import DataFrame # refactor opt. avoid pandas dependency

import hashlib # for checksums refactor opt. build functionality to check deployed scripts against source scripts also provide template checksum as well as rendered checksum?

from SecretManager import SecretManager;
from _vars import _schemachange_version, _snowflake_application_name, _err_oauth_tk_nm, _err_oauth_tk_err, _err_no_auth_mthd, _err_unsupported_auth_mthd, _warn_password, _warn_password_dup, _err_env_missing, _log_auth_type, _log_pk_enc, _log_okta_ep
#move exlusive items in as identified?... up to Jermey
from logging import getLogger

logger = getLogger(__name__)
### NOTES  creates two connections instead of one from the previous major refactoring
### using a seperate connection for reading and writing to the change history table makes it easier to manage the session state


class SnowflakeSchemachangeSession:
  """
  Manages Snowflake Interactions and authentication
  """
  #region Query Templates
  _q_ch_metadata =  "SELECT CREATED, LAST_ALTERED FROM {database_name}.INFORMATION_SCHEMA.TABLES" \
    + " WHERE TABLE_SCHEMA = REPLACE('{schema_name}','\"','') AND TABLE_NAME = replace('{table_name}','\"','')"
  _q_ch_schema_present = "SELECT COUNT(1) FROM {database_name}.INFORMATION_SCHEMA.SCHEMATA" \
    + " WHERE SCHEMA_NAME = REPLACE('{schema_name}','\"','')"
  _q_ch_ddl_schema = "CREATE SCHEMA {schema_name}"
  _q_ch_ddl_table = "CREATE TABLE IF NOT EXISTS {database_name}.{schema_name}.{table_name} (VERSION VARCHAR, " \
    + "DESCRIPTION VARCHAR, SCRIPT VARCHAR, SCRIPT_TYPE VARCHAR, CHECKSUM VARCHAR," \
    + " EXECUTION_TIME NUMBER, STATUS VARCHAR, INSTALLED_BY VARCHAR, INSTALLED_ON TIMESTAMP_LTZ)"
  _q_ch_r_checksum = "SELECT DISTINCT SCRIPT, FIRST_VALUE(CHECKSUM) OVER (PARTITION BY SCRIPT " \
    + "ORDER BY INSTALLED_ON DESC) FROM {database_name}.{schema_name}.{table_name} WHERE SCRIPT_TYPE = 'R' AND " \
    + "STATUS = 'Success'"
  _q_ch_fetch ="SELECT VERSION FROM {database_name}.{schema_name}.{table_name} WHERE SCRIPT_TYPE = 'V' ORDER" \
    + " BY INSTALLED_ON DESC LIMIT 1"
  _q_sess_tag = "ALTER SESSION SET QUERY_TAG = '{query_tag}'"
  _q_ch_log = "INSERT INTO {database_name}.{schema_name}.{table_name} (VERSION, DESCRIPTION, SCRIPT, SCRIPT_TYPE, " \
    + "CHECKSUM, EXECUTION_TIME, STATUS, INSTALLED_BY, INSTALLED_ON) values ('{script_version}'," \
    + "'{script_description}','{script_name}','{script_type}','{checksum}',{execution_time}," \
    + "'{status}','{user}',CURRENT_TIMESTAMP);"
  _q_set_sess_role = 'USE ROLE {role};'
  _q_set_sess_database = 'USE DATABASE {database};'
  _q_set_sess_schema = 'USE SCHEMA {schema};'
  _q_set_sess_warehouse = 'USE WAREHOUSE {warehouse};'
   #endregion Query Templates


  def __init__(self, config):
    session_parameters = {
        "QUERY_TAG": "schemachange %s" % _schemachange_version
        }
    if config.query_tag:
      session_parameters["QUERY_TAG"] += ";%s" % config.query_tag

    # Retreive Connection info from config dictionary
    self.conArgs = {"user": config.snowflake_user,"account": config.snowflake_account \
      ,"role": config.snowflake_role,"warehouse": config.snowflake_warehouse \
      ,"database": config.snowflake_database,"schema": config.snowflake_schema, "application": _snowflake_application_name \
      ,"session_parameters":session_parameters}

    self.oauth_config = config.oauth_config
    self.autocommit = config.autocommit
    self.verbose = config.verbose
    if self.set_connection_args():
      self.logging_connection = snowflake.connector.connect(**self.conArgs)
      self.script_apply_connection = snowflake.connector.connect(**self.conArgs)
      if not self.autocommit:
        self.script_apply_connection.autocommit(False) 
    else:
      print(_err_env_missing)
    self.log_cursor = self.logging_connection.cursor()
    self.script_cursor = self.script_apply_connection.cursor()
    # Set the inital State of the session used for reseting the session when a script is applied and changes these values 
    # in the Script_cursor's session
    # eg USE ROLE, USE WAREHOUSE; CREATE WAREHOUSE, USE DATABASE; CREATE DATABASE, USE SCHEMA; CREATE SCHEMA; USE 'X' skipping (DATABASE OR SCHEMA KEYWORD)
    self.role, self.warehouse, self.database, self.schema = self.get_session_state()

  def __del__(self):
    if hasattr(self, 'con'):
      self.con.close()

  def get_oauth_token(self):
    req_info = { \
      "url":self.oauth_config['token-provider-url'], \
      "headers":self.oauth_config['token-request-headers'], \
      "data":self.oauth_config['token-request-payload'] \
    }
    token_name = self.oauth_config['token-response-name']
    response = requests.post(**req_info)
    resJsonDict =json.loads(response.text)
    try: return resJsonDict[token_name]
    except KeyError:
      errormessage = _err_oauth_tk_nm.format(
        keys = ', '.join(resJsonDict.keys()),
        key = token_name
      )
      # if there is an error passed with the reponse include that
      if 'error_description' in resJsonDict.keys():
        errormessage += _err_oauth_tk_err.format(desc=resJsonDict['error_description'])
      raise KeyError( errormessage )

  def set_connection_args(self):
    # Password authentication is the default
    snowflake_password = None
    default_authenticator = 'snowflake'
    if os.getenv("SNOWFLAKE_PASSWORD") is not None and os.getenv("SNOWFLAKE_PASSWORD"):
      snowflake_password = os.getenv("SNOWFLAKE_PASSWORD")

    # Check legacy/deprecated env variable
    if os.getenv("SNOWSQL_PWD") is not None and os.getenv("SNOWSQL_PWD"):
      if snowflake_password:
        warnings.warn(_warn_password_dup, DeprecationWarning)
      else:
        warnings.warn(_warn_password, DeprecationWarning)
        snowflake_password = os.getenv("SNOWSQL_PWD")

    snowflake_authenticator = os.getenv("SNOWFLAKE_AUTHENTICATOR")
    logger.info("snowflake_authenticator: %s" % snowflake_authenticator)
    if snowflake_authenticator:
      # Determine the type of Authenticator
      # OAuth based authentication
      if snowflake_authenticator.lower() == 'oauth':
        oauth_token = self.get_oauth_token()

        if self.verbose:
          print( _log_auth_type % 'Oauth Access Token')
        self.conArgs['token'] = oauth_token
        self.conArgs['authenticator'] = 'oauth'
      # External Browswer based SSO
      elif snowflake_authenticator.lower() == 'externalbrowser':
        self.conArgs['authenticator'] = 'externalbrowser'
        if self.verbose:
          print(_log_auth_type % 'External Browser')
      # IDP based Authentication, limited to Okta
      elif snowflake_authenticator.lower()[:8]=='https://':

        if self.verbose:
          print(_log_auth_type % 'Okta')
          print(_log_okta_ep % snowflake_authenticator)

        self.conArgs['password'] = snowflake_password
        self.conArgs['authenticator'] = snowflake_authenticator.lower()
      elif snowflake_authenticator.lower() == 'snowflake':
        self.conArgs['authenticator'] = default_authenticator
      # if authenticator is not a supported method or the authenticator variable is defined but not specified
      else:
        # defaulting to snowflake as authenticator
        if self.verbose:
          print(_err_unsupported_auth_mthd.format(unsupported_authenticator=snowflake_authenticator) )
        self.conArgs['authenticator'] = default_authenticator
    else:
        # default authenticator to snowflake
        self.conArgs['authenticator'] = default_authenticator

    if self.conArgs['authenticator'].lower() == default_authenticator:
      # Giving preference to password based authentication when both private key and password are specified.
      if snowflake_password:
        if self.verbose:
          print(_log_auth_type %  'password' )
        self.conArgs['password'] = snowflake_password

      elif os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH", ''):
        if self.verbose:
          print( _log_auth_type %  'private key')

        private_key_password = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", '')
        if private_key_password:
          private_key_password = private_key_password.encode()
        else:
          private_key_password = None
          if self.verbose:
            print(_log_pk_enc)
        with open(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"], "rb") as key:
          p_key= serialization.load_pem_private_key(
              key.read(),
              password = private_key_password,
              backend = default_backend()
          )

        pkb = p_key.private_bytes(
            encoding = serialization.Encoding.DER,
            format = serialization.PrivateFormat.PKCS8,
            encryption_algorithm = serialization.NoEncryption())

        self.conArgs['private_key'] = pkb
      else:
        raise NameError(_err_no_auth_mthd)

    return True

  def execute_snowflake_script(self, query):
    if self.verbose:
      print(SecretManager.global_redact("SQL query: %s" % query))
    try:
      # res = self.con.execute_string(query)
      res = self.script_cursor.execute(query)
      if not self.autocommit:
        self.script_cursor.commit()
      return res
    except Exception as e:
      if not self.autocommit:
        self.script_cursor.rollback()
      raise e
    
  def get_session_state(self):
    return self.log_cursor.execute("SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()").fetchone()

  def fetch_change_history_metadata(self,change_history_table):
    # This should only ever return 0 or 1 rows
    query = self._q_ch_metadata.format(**change_history_table)
    results = self.log_cursor(query)

    # Collect all the results into a list
    change_history_metadata = dict()
    for cursor in results:
      for row in cursor:
        change_history_metadata['created'] = row[0]
        change_history_metadata['last_altered'] = row[1]

    return change_history_metadata

  def create_change_history_table_if_missing(self, change_history_table):
    # Check if schema exists
    query = self._q_ch_schema_present.format(**change_history_table)
    results = self.log_cursor.execute(query)
    schema_exists = False
    for cursor in results:
      for row in cursor:
        schema_exists = (row[0] > 0)

    # Create the schema if it doesn't exist
    if not schema_exists:
      query = self._q_ch_ddl_schema.format(**change_history_table)
      self.log_cursor.execute(query)

    # Finally, create the change history table if it doesn't exist
    query = self._q_ch_ddl_table.format(**change_history_table)
    self.log_cursor.execute(query)

  def fetch_r_scripts_checksum(self,change_history_table):
    query = self._q_ch_r_checksum.format(**change_history_table)
    results = self.log_cursor.execute(query)

    # Collect all the results into a dict
    d_script_checksum = DataFrame(columns=['script_name', 'checksum'])
    script_names = []
    checksums = []
    for cursor in results:
      for row in cursor:
        script_names.append(row[0])
        checksums.append(row[1])

    d_script_checksum['script_name'] = script_names
    d_script_checksum['checksum'] = checksums
    return d_script_checksum

  def fetch_change_history(self, change_history_table):
    query = self._q_ch_fetch.format(**change_history_table)
    results = self.log_cursor.execute(query)

    # Collect all the results into a list
    change_history = list()
    for cursor in results:
      for row in cursor:
        change_history.append(row[0])

    return change_history

  def reset_session(self):
    # These items are optional, so we can only reset the ones with values
    reset_query = ""
    if self.conArgs['role']:
      reset_query += self._q_set_sess_role.format(**self.conArgs) + " "
    if self.conArgs['warehouse']:
      reset_query += self._q_set_sess_warehouse.format(**self.conArgs) + " "
    if self.conArgs['database']:
      reset_query += self._q_set_sess_database.format(**self.conArgs) + " "
    if self.conArgs['schema']:
      reset_query += self._q_set_sess_schema.format(**self.conArgs) + " "

    self.execute_snowflake_script(reset_query)

  def reset_query_tag(self, extra_tag = None):
    query_tag = self.conArgs["session_parameters"]["QUERY_TAG"]
    if extra_tag:
      query_tag += f";{extra_tag}"

    self.execute_snowflake_script(self._q_sess_tag.format(query_tag=query_tag))

  def apply_change_script(self, script, script_content, change_history_table):
    # Define a few other change related variables
    checksum = hashlib.sha224(script_content.encode('utf-8')).hexdigest()
    execution_time = 0
    status = 'Success'

    # Execute the contents of the script
    if len(script_content) > 0:
      start = time.time()
      self.reset_session()
      self.reset_query_tag(script['script_name'])
      self.execute_snowflake_script(script_content)
      self.reset_query_tag() 
      end = time.time()
      execution_time = round(end - start)

    # Finally record this change in the change history table by gathering data
    frmt_args = script.copy()
    frmt_args.update(change_history_table)
    frmt_args['checksum'] =checksum
    frmt_args['execution_time'] =execution_time
    frmt_args['status'] =status
    frmt_args['user'] =self.conArgs['user']
    # Compose and execute the insert statement to the log file
    query = self._q_ch_log.format(**frmt_args)
    self.log_cursor(query)
