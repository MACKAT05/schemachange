#notes this contains most of the global variables used in the schemachange project and strings 21 -78

#region Global Variables
# metadata
_schemachange_version = '3.6.1'
_config_file_name = 'schemachange-config.yml'
_target_file_name = 'schemachange-target.yml'
_metadata_database_name = 'METADATA'
_metadata_schema_name = 'SCHEMACHANGE'
_metadata_table_name = 'CHANGE_HISTORY'
_snowflake_application_name = 'schemachange'

# messages
_err_jinja_env_var = "Could not find environmental variable %s and no default" \
  + " value was provided"
_err_oauth_tk_nm = 'Response Json contains keys: {keys} \n but not {key}'
_err_oauth_tk_err = '\n error description: {desc}'
_err_no_auth_mthd = "Unable to find connection credentials for Okta, private key,  " \
  + "password, Oauth or Browser authentication"
_err_unsupported_auth_mthd = "'{unsupported_authenticator}' is not supported authenticator option. " \
  + "Choose from externalbrowser, oauth, https://<subdomain>.okta.com. Using default value = 'snowflake'"
_warn_password = "The SNOWSQL_PWD environment variable is deprecated and will" \
  + " be removed in a later version of schemachange. Please use SNOWFLAKE_PASSWORD instead."
_warn_password_dup = "Environment variables SNOWFLAKE_PASSWORD and SNOWSQL_PWD are " \
  + " both present, using SNOWFLAKE_PASSWORD"
_err_args_missing ="Missing config values. The following config values are required: %s "
_err_env_missing ="Missing environment variable(s). \nSNOWFLAKE_PASSWORD must be defined for " \
  + "password authentication. \nSNOWFLAKE_PRIVATE_KEY_PATH and (optional) " \
  + "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE must be defined for private key authentication. " \
  + "\nSNOWFLAKE_AUTHENTICATOR must be defined is using Oauth, OKTA or external Browser Authentication."
_log_config_details = "Using Snowflake account {snowflake_account}\nUsing default role " \
  + "{snowflake_role}\nUsing default warehouse {snowflake_warehouse}\nUsing default " \
  + "database {snowflake_database}" \
  + "schema {snowflake_schema}"
_log_ch_use = "Using change history table {database_name}.{schema_name}.{table_name} " \
  + "(last altered {last_altered})"
_log_ch_create = "Created change history table {database_name}.{schema_name}.{table_name}"
_err_ch_missing = "Unable to find change history table {database_name}.{schema_name}.{table_name}"
_log_ch_max_version = "Max applied change script version: {max_published_version_display}"
_log_skip_v = "Skipping change script {script_name} because it's older than the most recently " \
  + "applied change ({max_published_version})"
_log_skip_r ="Skipping change script {script_name} because there is no change since the last " \
  + "execution"
_log_apply =  "Applying change script {script_name}"
_log_apply_set_complete  =  "Successfully applied {scripts_applied} change scripts (skipping " \
  + "{scripts_skipped}) \nCompleted successfully"
_err_vars_config = "vars did not parse correctly, please check its configuration"
_err_vars_reserved = "The variable schemachange has been reserved for use by schemachange, " \
  + "please use a different name"
_err_invalid_folder  = "Invalid {folder_type} folder: {path}"
_err_dup_scripts = "The script name {script_name} exists more than once (first_instance " \
  + "{first_path}, second instance {script_full_path})"
_err_dup_scripts_version = "The script version {script_version} exists more than once " \
  + "(second instance {script_full_path})"
_err_invalid_cht  = 'Invalid change history table name: %s'
_log_auth_type ="Proceeding with %s authentication"
_log_pk_enc ="No private key passphrase provided. Assuming the key is not encrypted."
_log_okta_ep ="Okta Endpoint: %s"

#endregion Global Variables