
import os
from typing import Any, Dict, Set
import textwrap
import yaml
import json

from JinjaTemplateProcessor import JinjaTemplateProcessor,JinjaEnvVar
from _vars import _config_file_name, _err_invalid_folder, _err_vars_config, _err_vars_reserved, _target_file_name
from SecretManager import SecretManager
from jinja2 import Template, StrictUndefined 
from logging import getLogger

#notes:
# this is very much a revamped wiring and expansion of the configuration handling.
#861-890 in cli_original
#get_schemachange_config;extract_config_secrets add_range

logger = getLogger(__name__)


def extract_config_secrets(config: Dict[str, Any]) -> Set[str]:
  """
  Extracts all secret values from the vars attributes in config
  """

  # defined as an inner/ nested function to provide encapsulation
  def inner_extract_dictionary_secrets(dictionary: Dict[str, Any], child_of_secrets: bool = False) -> Set[str]:
    """
    Considers any key with the word secret in the name as a secret or
    all values as secrets if a child of a key named secrets.
    """
    extracted_secrets: Set[str] = set()

    if dictionary:
      for (key, value) in dictionary.items():
        if isinstance(value, dict):
          if key == "secrets":
            extracted_secrets = extracted_secrets | inner_extract_dictionary_secrets(value, True)
          else :
            extracted_secrets = extracted_secrets | inner_extract_dictionary_secrets(value, child_of_secrets)
        elif child_of_secrets or "SECRET" in key.upper():
          extracted_secrets.add(value.strip())
    return extracted_secrets

  extracted = set()

  if config:
    if "vars" in config:
      extracted = inner_extract_dictionary_secrets(config["vars"])
  return extracted

class schemachange_config():
    def __init__(self,args) -> None:
        # deal with logging level 1st
        if args.verbose in ['True','true','TRUE','1','yes','Yes','YES','y','Y','DEBUG','debug','Debug','10', True]:
            logger.setLevel('DEBUG')
        elif args.verbose in ['CRITICAL','ERROR','WARNING','INFO',20,30,40,50 ]:
            logger.setLevel(args.verbose)
        else:
            logger.setLevel('INFO')

        #deal with targets as neeeded 
        if args.target_folder:
            target_file_path  = os.path.join(args.target_folder, _target_file_name) 
            logger.info("Using target file %s" % target_file_path)
            if os.path.isfile(target_file_path):
                with open(target_file_path) as target_file:
                   target_jinja = Template(target_file.read(), undefined=StrictUndefined, extensions=[JinjaEnvVar]).render()
                   try:
                       self.target_envs  = yaml.full_load(target_jinja)['targets']
                       self.targets = list(self.target_envs.keys())
                   except:
                       logger.error("Error parsing target file %s" % target_file_path)
                       if args.subcommand in ['render-deployment-to-folder','check-deployment-status']:
                            raise ValueError("Error parsing target file %s" % target_file_path)
                       else:
                          logger.info("Using default target of execution environment for %s" % args.subcommand)
                          self.targets = ['Default']
                          self.target_envs = {'Default':{}}
        if not hasattr(self, 'targets'):
               #create a single target with no overrides
               logger.info("No target file found at %s" % args.target_folder)
               self.targets = ['Default']
               self.target_envs = {'Default':{}}
        
        #load config file and retain as jinja template if multiple targets need to be rendered from it
        if args.config_folder:
            config_file_path  = os.path.join(args.config_folder, _config_file_name)
            if os.path.isfile(config_file_path):
                print("Using config file: %s" % config_file_path)
                with open(config_file_path) as config_file:
                   self.config_jinja = Template(config_file.read(), undefined=StrictUndefined, extensions=[JinjaEnvVar]) 
        
        # Retreive argparser attributes as dictionary
        self.cli_args = args.__dict__.copy() 

        #nullify expected null values for render.
        if args.subcommand == 'render':
            renderoveride = {"snowflake_account":None,"snowflake_user":None,"snowflake_role":None, \
            "snowflake_warehouse":None,"snowflake_database":None,"change_history_table":None, \
            "snowflake_schema":None,"create_change_history_table":None,"autocommit":None, \
            "dry_run":None,"query_tag":None,"oauth_config":None }
            # if verbose is set to debug then we want to see the rendered config
            if logger.level == 10:
                for key,value in renderoveride.items():
                    if key in self.cli_args.keys():
                        if self.cli_args[key]:
                            logger.debug("Overriding %s with %s for render command" % (key,self.cli_args[key]))
                            renderoveride[key] = self.cli_args[key] 
            else:
                self.cli_args.update(renderoveride)


        self.set_environment()
       
    def set_environment(self, env:str =''):
        if env == '':
            env = self.targets[0]
        if env in self.target_envs:
            for key,value in self.target_envs[env].items():
                logger.info("Setting environment variable %s to %s" % (key,value))
                os.environ[key] = value 
        self.target_name = env
        config = self.merge_config_file_w_cmd_line()
        # setup a secret manager and assign to global scope
        
        # set attributes from config
        for key in config.keys():
            setattr(self, key, config[key])


        sm = SecretManager()
        SecretManager.set_global_manager(sm)
        # Extract all secrets for --vars
        sm.add_range(extract_config_secrets(config))

        # Then log some details
        logger.info("Using root folder %s" % config['root_folder'])
        if config['modules_folder']:
            logger.info("Using Jinja modules folder %s" % config['modules_folder'])

        # pretty print the variables in yaml style
        if config['vars'] == {}:
            logger.info("Using variables: {}")
        else:
            logger.info("Using variables:")
            logger.info(textwrap.indent( \
            SecretManager.global_redact(yaml.dump( \
                config['vars'], \
                sort_keys=False, \
                default_flow_style=False)), prefix = "  "))
        self.jinja_processor = JinjaTemplateProcessor(config)
       
    def merge_config_file_w_cmd_line(self): 
        # create cli override dictionary
        cli_inputs_keys = set(['root_folder', 'modules_folder', 'snowflake_account', \
            'snowflake_user', 'snowflake_role', 'snowflake_warehouse', 'snowflake_database', \
            'snowflake_schema', 'change_history_table', 'vars', 'create_change_history_table', \
            'autocommit', 'verbose', 'dry_run', 'query_tag', 'oauth_config'])
        if logger.level == 10:
            for key,value in self.cli_args.items():
                if key in cli_inputs_keys:
                    logger.debug("found argument %s with %s" % (key,value))
        cli_inputs = {k:v for (k,v) in self.cli_args.items() if k in cli_inputs_keys and v} 
        
        #handle vars and oauth_config as dictionaries since strings are passed from cli
        if 'vars' in cli_inputs.keys():
            if type(cli_inputs['vars']) is not dict:
                logger.debug("Converting vars cli string to dictionary")
                try:
                    vars_dict = json.loads(cli_inputs['vars'].replace("'",'"'))
                    cli_inputs['vars'] = vars_dict
                except:
                    logger.error("Error parsing vars string as dictionary")
                    if self.cli_args.subcommand =='deploy':
                        raise ValueError("Error parsing vars string as dictionary")
        if 'oauth_config' in cli_inputs.keys():
            if type(cli_inputs['oauth_config']) is not dict:
                logger.debug("Converting ouath-config cli string to dictionary")
                try:
                    vars_dict = json.loads(cli_inputs['oauth_config'].replace("'",'"'))
                    cli_inputs['oauth_config'] = vars_dict
                except:
                    logger.error("Error parsing oauth-config string as dictionary")
                    if self.cli_args.subcommand =='deploy':
                        raise ValueError("Error parsing oauth-config string as dictionary")

        with open(os.path.join(self.cli_args['config_folder'], _config_file_name)) as config_file:
            self.config_jinja = Template(config_file.read(), undefined=StrictUndefined, extensions=[JinjaEnvVar]) 


        # load YAML inputs and convert kebabs to snakes
        config = {k.replace('-','_'):v for (k,v) in yaml.full_load(self.config_jinja.render()).items()}
        if logger.level == 10:
            for key,value in config.items():
                logger.debug("found config %s with %s" % (key,value))
                if key in cli_inputs.keys():
                    logger.debug("Overriding config file yaml entry %s with %s from cli input" % (key.replace('_','-'),cli_inputs[key]))

        # create Default values dictionary
        config_defaults =  {"root_folder":os.path.abspath('.'), "modules_folder":None,  \
            "snowflake_account":None,  "snowflake_user":None, "snowflake_role":None,   \
            "snowflake_warehouse":None,  "snowflake_database":None, "snowflake_schema":None, \
            "change_history_table":None,  "vars":{}, "create_change_history_table":False, \
            "autocommit":False, "verbose":False,  "dry_run":False , "query_tag":None ,\
            "oauth_config":None }
        #insert defualt values for items not populated
        config.update({ k:v for (k,v) in config_defaults.items() if not k in config.keys()})

        cli_inputs.update({ k:v for (k,v) in config.items() if not k in cli_inputs.keys()})
        # Validate folder paths
        if 'root_folder' in cli_inputs:
            cli_inputs['root_folder'] = os.path.abspath(cli_inputs['root_folder'])
        if not os.path.isdir(cli_inputs['root_folder']):
            raise ValueError(_err_invalid_folder.format(folder_type='root', path=cli_inputs['root_folder']))

        if cli_inputs['modules_folder']:
            print(cli_inputs['modules_folder'])
            if not os.path.isdir(cli_inputs['modules_folder']):
                raise ValueError(_err_invalid_folder.format(folder_type='modules', path=cli_inputs['modules_folder']))
        if cli_inputs['vars']:
            # if vars is configured wrong in the config file it will come through as a string
            if type(cli_inputs['vars']) is not dict:
                raise ValueError(_err_vars_config)

            # the variable schema change has been reserved
        if "schemachange" in cli_inputs['vars']:
           raise ValueError(_err_vars_reserved)
        return cli_inputs
  

        # req_args = set(['snowflake_account','snowflake_user','snowflake_role','snowflake_warehouse'])
        # provided_args = {k:v for (k,v) in config.items() if v}
        # missing_args = req_args -provided_args.keys()
        # if len(missing_args)>0:
        #     raise ValueError(_err_args_missing % ', '.join({s.replace('_', ' ') for s in missing_args}))

        # #ensure an authentication method is specified / present. one of the below needs to be present.
        # req_env_var = set(['SNOWFLAKE_PASSWORD', 'SNOWSQL_PWD','SNOWFLAKE_PRIVATE_KEY_PATH','SNOWFLAKE_AUTHENTICATOR'])
        # if len((req_env_var - dict(environ).keys()))==len(req_env_var):
        #     raise ValueError(_err_env_missing)
