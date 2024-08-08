from _vars import _err_args_missing, _err_env_missing, _log_config_details, _log_ch_use, _log_ch_create, _err_ch_missing, _log_ch_max_version, _log_skip_v, _log_apply, _log_skip_r, _err_dup_scripts, _err_dup_scripts_version, _err_invalid_cht, _metadata_database_name, _metadata_schema_name, _metadata_table_name

from SnowflakeSchemachangeSession import SnowflakeSchemachangeSession
 
import multiprocessing
from schemachangetarget import schemachange_target
from commandconfig import schemachange_config
from os import environ

##schemaChangeDeployment iterater and validator for targets
# schemachangeDepoymnetTarget container for legacy behaviour of deploy

from logging import getLogger

logger = getLogger(__name__)


class schemaChangeDeployment:
    def __init__(self, config:schemachange_config):
        self.config = config
        logger.debug("schemachangedeployment object created")  
        self.session = SnowflakeSchemachangeSession(config)
        #self.targets = self.Multiprocess_targets()

    def Multiprocess_targets(self):
        def target_function(target, config, queue):
            # replace this with the actual code to create a schemachange_target object
            return_target = schemachange_target(config, self.session)
            queue.put(return_target)

        schemachange_targets = []
        for target in self.config.targets:
            # set environment variables here
            self.config.set_environment (target)

            queue = multiprocessing.Queue()
            process = multiprocessing.Process(target=target_function, args=(target, self.config, queue))
            process.start()
            process.join()

            schemachange_targets.append(queue.get())

        return schemachange_targets
    def execute(self):
        match self.config.command:
            case "deploy":
                self.deploy()
            case "render":
                self.render()
            case "render-deployment-to-folder":
                self.render_deployment_to_folder()
            case "check-deployment-status":
                self.check_deployment_status() 
            case _:
                raise ValueError(_err_args_missing.format(args=self.config.command))
    def deploy(self):
        #parse scritps in the default deployment 
        schemachange_deploy_target = schemachange_target(self.config, self.session)
        schemachange_deploy_target.deploy()
    def render(self):
        script = schemachangescript(self.config.script_path, self.config.jinja_processor)
        logger.info(str(script))

    def render_deployment_to_folder(self):
        schemachange_deploy_targets = self.Multiprocess_targets()
        for schemachange_deploy_target  in schemachange_deploy_targets:
            path = self.config.render_path +  ('/' + schemachange_deploy_target.target_name if len(self.config.targets) > 1 else '/') 
            schemachange_deploy_target.render_deployment_to_folder(path)

    def check_deployment_status(self):
        schemachange_deploy_targets = self.Multiprocess_targets()
        compare_index = []
        for schemachange_deploy_target  in schemachange_deploy_targets:
            schemachange_deploy_target.get_statuses()
            compare_index.append(schemachange_deploy_target.all_scripts.keys())
        index = [item for sublist in compare_index for item in sublist]
        for script in index:
            for schemachange_deploy_target  in schemachange_deploy_targets:
                if script in schemachange_deploy_target.all_scripts.keys():
                    print(schemachange_deploy_target.all_scripts[script].status)
                else:
                    print("{1} Not Found in Target {2}".format(script,  schemachange_deploy_target.target_name))  
        
