import argparse
import json

#Note: covers 813-842

def ArgParser():
  parser = argparse.ArgumentParser(prog = 'schemachange', description = 'Apply schema changes to a Snowflake account. Full readme at https://github.com/Snowflake-Labs/schemachange', formatter_class = argparse.RawTextHelpFormatter)
  subcommands = parser.add_subparsers(dest='subcommand')

  parser_deploy = subcommands.add_parser("deploy")
  parser_deploy.add_argument('--config-folder', type = str, default = '.', help = 'The folder to look in for the schemachange-config.yml file (the default is the current working directory)', required = False)
  parser_deploy.add_argument('-f', '--root-folder', type = str, help = 'The root folder for the database change scripts', required = False)
  parser_deploy.add_argument('-m', '--modules-folder', type = str, help = 'The modules folder for jinja macros and templates to be used across multiple scripts', required = False)
  parser_deploy.add_argument('-a', '--snowflake-account', type = str, help = 'The name of the snowflake account (e.g. xy12345.east-us-2.azure)', required = False)
  parser_deploy.add_argument('-u', '--snowflake-user', type = str, help = 'The name of the snowflake user', required = False)
  parser_deploy.add_argument('-r', '--snowflake-role', type = str, help = 'The name of the default role to use', required = False)
  parser_deploy.add_argument('-w', '--snowflake-warehouse', type = str, help = 'The name of the default warehouse to use. Can be overridden in the change scripts.', required = False)
  parser_deploy.add_argument('-d', '--snowflake-database', type = str, help = 'The name of the default database to use. Can be overridden in the change scripts.', required = False)
  parser_deploy.add_argument('-s', '--snowflake-schema', type = str, help = 'The name of the default schema to use. Can be overridden in the change scripts.', required = False)
  parser_deploy.add_argument('-c', '--change-history-table', type = str, help = 'Used to override the default name of the change history table (the default is METADATA.SCHEMACHANGE.CHANGE_HISTORY)', required = False)
  parser_deploy.add_argument('--vars', type = json.loads, help = 'Define values for the variables to replaced in change scripts, given in JSON format (e.g. {"variable1": "value1", "variable2": "value2"})', required = False)
  parser_deploy.add_argument('--create-change-history-table', action='store_true', help = 'Create the change history schema and table, if they do not exist (the default is False)', required = False)
  parser_deploy.add_argument('-ac', '--autocommit', action='store_true', help = 'Enable autocommit feature for DML commands (the default is False)', required = False)
  parser_deploy.add_argument('-v','--verbose', action='store', help = 'Display verbose debugging details during execution (the default is Logging.Info)', required = False)
  #TODO: test CLI with no args after modificaiton
  parser_deploy.add_argument('--dry-run', action='store_true', help = 'Run schemachange in dry run mode (the default is False)', required = False)
  parser_deploy.add_argument('--query-tag', type = str, help = 'The string to add to the Snowflake QUERY_TAG session value for each query executed', required = False)
  parser_deploy.add_argument('--oauth-config', type = json.loads, help = 'Define values for the variables to Make Oauth Token requests  (e.g. {"token-provider-url": "https//...", "token-request-payload": {"client_id": "GUID_xyz",...},... })', required = False)
   # TODO test CLI passing of args

  parser_render = subcommands.add_parser('render', description="Renders a script to the console, used to check and verify jinja output from scripts.")
  parser_render.add_argument('--config-folder', type = str, default = '.', help = 'The folder to look in for the schemachange-config.yml file (the default is the current working directory)', required = False)
  parser_render.add_argument('-f', '--root-folder', type = str, help = 'The root folder for the database change scripts', required = False)
  parser_render.add_argument('-m', '--modules-folder', type = str, help = 'The modules folder for jinja macros and templates to be used across multiple scripts', required = False)
  parser_render.add_argument('--vars', type = json.loads, help = 'Define values for the variables to replaced in change scripts, given in JSON format (e.g. {"variable1": "value1", "variable2": "value2"})', required = False)
  parser_render.add_argument('-v', '--verbose', action='store', help = 'Display verbose debugging details during execution (the default is Logging.Info)', required = False)
  parser_render.add_argument('script', type = str, help = 'The script to render')

  parser_render_deployment_to_folder = subcommands.add_parser('render-deployment-to-folder', description="Renders a script or everything in the specified path to a folder as if it were being deployed, used to check and verify jinja output from scripts as well as what will deploy to snowflake.")
  parser_render_deployment_to_folder.add_argument('--config-folder', type = str, default = '.', help = 'The folder to look in for the schemachange-config.yml file (the default is the current working directory)', required = False)
  parser_render_deployment_to_folder.add_argument('-f', '--root-folder', type = str, help = 'The root folder for the database change scripts', required = False)
  parser_render_deployment_to_folder.add_argument('-m', '--modules-folder', type = str, help = 'The modules folder for jinja macros and templates to be used across multiple scripts', required = False) 
  parser_render_deployment_to_folder.add_argument('-a', '--snowflake-account', type = str, help = 'The name of the snowflake account (e.g. xy12345.east-us-2.azure)', required = False)
  parser_render_deployment_to_folder.add_argument('-u', '--snowflake-user', type = str, help = 'The name of the snowflake user', required = False)
  parser_render_deployment_to_folder.add_argument('-r', '--snowflake-role', type = str, help = 'The name of the default role to use', required = False)
  parser_render_deployment_to_folder.add_argument('-w', '--snowflake-warehouse', type = str, help = 'The name of the default warehouse to use. Can be overridden in the change scripts.', required = False)
  parser_render_deployment_to_folder.add_argument('-d', '--snowflake-database', type = str, help = 'The name of the default database to use. Can be overridden in the change scripts.', required = False)
  parser_render_deployment_to_folder.add_argument('-s', '--snowflake-schema', type = str, help = 'The name of the default schema to use. Can be overridden in the change scripts.', required = False)
  parser_render_deployment_to_folder.add_argument('-c', '--change-history-table', type = str, help = 'Used to override the default name of the change history table (the default is METADATA.SCHEMACHANGE.CHANGE_HISTORY)', required = False)
  parser_render_deployment_to_folder.add_argument('--vars', type = json.loads, help = 'Define values for the variables to replaced in change scripts, given in JSON format (e.g. {"variable1": "value1", "variable2": "value2"})', required = False)   
  parser_render_deployment_to_folder.add_argument('-v', '--verbose', action='store', help = 'Display verbose debugging details during execution (the default is Logging.Info)', required = False)
  #TODO: test CLI with no args after modificaiton
  parser_render_deployment_to_folder.add_argument('-rp','--render-path', type = str, default = './renders/', help = 'The path to output rendered scripts to (the default is the current working directory /renders/)', required = False)
 
  parser_check_deployment_status = subcommands.add_parser('check-deployment-status', description="Checks the status of a deployment, used to get what would be deployed. optionally use a schemachange-targets.yml file to iterate over multiple deployment targets.")
  parser_check_deployment_status.add_argument('--config-folder', type = str, default = '.', help = 'The folder to look in for the schemachange-config.yml file (the default is the current working directory)', required = False)
  parser_check_deployment_status.add_argument('-f', '--root-folder', type = str, help = 'The root folder for the database change scripts', required = False)
  parser_check_deployment_status.add_argument('-m', '--modules-folder', type = str, help = 'The modules folder for jinja macros and templates to be used across multiple scripts', required = False)
  parser_check_deployment_status.add_argument('-a', '--snowflake-account', type = str, help = 'The name of the snowflake account (e.g. xy12345.east-us-2.azure)', required = False)
  parser_check_deployment_status.add_argument('-u', '--snowflake-user', type = str, help = 'The name of the snowflake user', required = False)
  parser_check_deployment_status.add_argument('-r', '--snowflake-role', type = str, help = 'The name of the default role to use', required = False)
  parser_check_deployment_status.add_argument('-w', '--snowflake-warehouse', type = str, help = 'The name of the default warehouse to use. Can be overridden in the change scripts.', required = False)
  parser_check_deployment_status.add_argument('-d', '--snowflake-database', type = str, help = 'The name of the default database to use. Can be overridden in the change scripts.', required = False)
  parser_check_deployment_status.add_argument('-s', '--snowflake-schema', type = str, help = 'The name of the default schema to use. Can be overridden in the change scripts.', required = False) 
  parser_check_deployment_status.add_argument('-c', '--change-history-table', type = str, help = 'Used to override the default name of the change history table (the default is METADATA.SCHEMACHANGE.CHANGE_HISTORY)', required = False)
  parser_check_deployment_status.add_argument('--vars', type = json.loads, help = 'Define values for the variables to replaced in change scripts, given in JSON format (e.g. {"variable1": "value1", "variable2": "value2"})', required = False)
  parser_check_deployment_status.add_argument('-v', '--verbose', action='store_true', help = 'Display verbose debugging details during execution (the default is False)', required = False)
  parser_check_deployment_status.add_argument('-t', '--target-folder', type = str, default = '.', help = 'The path to a schemachange-targets.yml file to iterate over multiple deployment targets default is root directory', required = False)  
  parser_check_deployment_status.add_argument('-o','--output', type = str, default = './deployment-status.txt', help = 'The path to output deployment status to (the default is the current working directory /deployment-status.txt)', required = False)
  return parser
