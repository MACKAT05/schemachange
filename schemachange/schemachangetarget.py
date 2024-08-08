
from commandconfig import schemachange_config
from SnowflakeSchemachangeSession import SnowflakeSchemachangeSession
from _vars import _metadata_database_name,_err_dup_scripts, _metadata_schema_name,_err_invalid_cht,_log_ch_use,_err_ch_missing,_log_ch_create, _metadata_table_name, _log_ch_use, _err_dup_scripts_version
from schemachangescript import schemaChangeScript
import os
import re
import multiprocessing

from logging import getLogger

logger = getLogger(__name__)

_q_ch_fetch ="SELECT VERSION FROM {database_name}.{schema_name}.{table_name} WHERE SCRIPT_TYPE = 'V' ORDER" \
    + " BY INSTALLED_ON DESC LIMIT 1"
_q_deployment_stats = "SELECT SCRIPT_TYPE, COUNT(CHECKSUM) COUNT,COUNT(DISTINCT CHECKSUM) DISTINCT_COUNT  FROM \
                        {database_name}.{schema_name}.{table_name} GROUP BY SCRIPT_TYPE"

class schemachange_target:
    scripts_applied = 0
    scripts_skipped = 0
    
    def __init__(self, cc: schemachange_config, session:SnowflakeSchemachangeSession):
        self.cc = cc 
        self.session = session  
        self.unorderedscripts = self.get_all_scripts_recursively()
    def get_statuses(self):
        vscript = self.session.execute(_q_ch_fetch.format(**self.cc.change_history_table))[0]
        def get_status(script,session):
            return script.get_status()
        statuspool = multiprocessing.Pool()
        statuses = [statuspool.apply_async(get_status, (script,self.session)) for script in self.orderedscripts]
        statuspool.join()
        return statuses
    def deploy(self):
        # must follow the order of the scripts
        for script in self.get_scripts_in_deploy_order():
            logger.info(f"Processing script {script.script_name}")
            script.deploy(self.session)

    def render_deployment_to_folder(self,path):
        def render_script(script):
            script.render(path)
        writepool = multiprocessing.Pool()
        [writepool.apply_async(render_script, (script,)) for script in self.all_scripts]
        writepool.close()
        writepool.join()
        

    def get_all_scripts_recursively(self):
        all_files = dict()
        all_versions = list()
        duplicate_scripts = list()
        duplicate_versions = list()
        for root, dirs, files in os.walk(self.cc.project_root):
            for file in files:
                file_full_path = os.path.join(root, file)
                #this should be faster than a regex
                check = file.split('__')
                if len(check) == 2  and check[0][0] in ['V', 'R', 'A'] and (check[1].lower().endswith('.sql') or check[1].lower().endswith('.sql.jinja')):
                    if file in all_files:
                        duplicate_scripts.append((file_full_path, all_files[file]))
                    else:
                        all_files[file] = file_full_path
                    if self.cc.verbose:
                        m = {'R':'Repeatable', 'V':'Versioned', 'A':'Always'}
                        r= m.get(file[0])
                        logger.info(f"Found {r} file {file_full_path}")
                    if file[0] == 'V':
                        if check[1:] not in all_versions:
                            duplicate_versions.append((script, all_files[script.script_name].script_path))
                            #raise ValueError(_err_dup_scripts_version.format(**script))
                        else:
                            all_versions.append(check[1:])
                else:
                    if self.cc.verbose:
                        logger.debug(f"Skipping non-change script file {file_full_path}")
        
        def process_script(file_full_path, jinja_processor):
            script = schemaChangeScript(file_full_path, jinja_processor)
            # Process the script here

        # Create a pool of processes
        pool = multiprocessing.Pool()

        # Use the pool to process each script in parallel
        results = [pool.apply_async(process_script, (file_full_path, self.jinja_processor)) for file_full_path in all_files.values()]

        # Wait for all processes to complete
        pool.close()
        pool.join()

        # Get the results (if needed)
        self.all_scripts = [result.get() for result in results]
        parse_errors = [script for script in all_files.values() if script.parse_errors]
         
        if duplicate_scripts or duplicate_versions or parse_errors:
            for script, first_path in duplicate_scripts:
                print(_err_dup_scripts.format(script_name=script.name, first_path=first_path, script_full_path=script.file_full_path))
            for script, first_path in duplicate_versions:
                print(_err_dup_scripts.format(script_name=script.name, first_path=first_path, script_full_path=script.file_full_path))
            for script in parse_errors:
                print(script.parse_errors)
            raise SystemError('Duplicate scripts or version found or errors parsing scripts')
    def get_scripts_in_deploy_order(self):
        def sorted_alphanumeric(data):
             return sorted(data, key=get_alphanum_key)
        def get_alphanum_key(key):
            convert = lambda text: int(text) if text.isdigit() else text.lower()
            alphanum_key = [ convert(c) for c in re.split('([0-9]+)', key) ]
            return alphanum_key
        sorted =sorted_alphanumeric(self.unorderedscripts.values())
        sorted =   [script for script in sorted if script.name[0] == 'V'] \
                 + [script for script in sorted if script.name[0] == 'R'] \
                 + [script for script in sorted if script.name[0] == 'A']
        return  sorted





# class change_history_table:
#     exists = None
#     def __init__(self, cc: schemachange_config, session:SnowflakeSchemachangeSession):
#         self.cc = cc
#         self.session = session

#         change_history_table = self.resolve_change_history_table_name()
#         change_history_metadata = session.fetch_change_history_metadata(change_history_table)
#         if change_history_metadata:
#             print(_log_ch_use.format(last_altered=change_history_metadata['last_altered'], **change_history_table))
#         elif cc.create_change_history_table:
#             # Create the change history table (and containing objects) if it don't exist.
#             if not cc.dry_run:
#                 self.session.create_change_history_table_if_missing(change_history_table)
#             print(_log_ch_create.format(**change_history_table))
#         else:
#             raise ValueError(_err_ch_missing.format(**change_history_table))
#     def resolve_change_history_table_name(self): 
#         # Start with the global defaults
#         details = dict()
#         details['database_name'] = _metadata_database_name
#         details['schema_name'] = _metadata_schema_name
#         details['table_name'] = _metadata_table_name

#         # Then override the defaults if requested. The name could be in one, two or three part notation.
#         if self.cc.change_history_table is not None:
#             table_name_parts = self.cc.change_history_table.strip().split('.')
#             if len(table_name_parts) == 1:
#                 details['table_name'] = table_name_parts[0]
#             elif len(table_name_parts) == 2:
#                 details['table_name'] = table_name_parts[1]
#                 details['schema_name'] = table_name_parts[0]
#             elif len(table_name_parts) == 3:
#                 details['table_name'] = table_name_parts[2]
#                 details['schema_name'] = table_name_parts[1]
#                 details['database_name'] = table_name_parts[0]
#             else:
#                 raise ValueError(_err_invalid_cht % self.cc.change_history_table)
#         #if the object name does not include '"' raise to upper case on return
#         return {k:v if '"' in v else v.upper() for (k,v) in details.items()}