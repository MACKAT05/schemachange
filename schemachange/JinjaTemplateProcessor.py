
from typing import Dict, Any,Optional
import jinja2
import jinja2.ext
from jinja2.loaders import BaseLoader  
from  os import environ
#from commandconfig import schemachange_config as com
import csv

from _vars import _err_jinja_env_var;
from logging import getLogger

logger = getLogger(__name__)


class JinjaEnvVar(jinja2.ext.Extension):
  """
  Extends Jinja Templates with access to environmental variables
  """
  def __init__(self, environment: jinja2.Environment):
    super().__init__(environment)

    # add globals
    environment.globals["env_var"] = JinjaEnvVar.env_var
    environment.globals["from_csv"] = JinjaEnvVar.from_csv

  @staticmethod
  def env_var(env_var: str, default: Optional[str] = None) -> str:
    """
    Returns the value of the environmental variable or the default.
    """
    result = default
    if env_var in environ:
      result = environ[env_var]

    if result is None:
      raise ValueError(_err_jinja_env_var % env_var)

    return result

  @staticmethod
  def from_csv(file_path: str,delimiter:Optional[str] = ',',quotechar:Optional[str] = '"',escapechar:Optional[str] ='\\') -> list:
    """
    Reads a CSV file and returns the data as a list.
    """
    data = []
    with open(file_path, 'r') as file:
      csv_reader = csv.reader(file, delimiter=delimiter, quotechar=quotechar,escapechar=escapechar)
      for row in csv_reader:
        data.append(row)
    return data

class JinjaTemplateProcessor:
  _env_args = {"undefined":jinja2.StrictUndefined,"autoescape":False, "extensions":[JinjaEnvVar]}

  def __init__(self,cc ):
    self.cc = cc
    self.set_jinja_env(cc)

  def set_jinja_env(self, cc):
    loader: BaseLoader
    if cc['modules_folder']:
      loader = jinja2.ChoiceLoader(
        [
          jinja2.FileSystemLoader(cc['root_folder']),
          jinja2.PrefixLoader({"modules": jinja2.FileSystemLoader(cc['modules_folder'])}),
        ]
      )
    else:
      loader = jinja2.FileSystemLoader(cc['root_folder'])
    self.__environment = jinja2.Environment(loader=loader, **self._env_args)
    self.__project_root = cc['root_folder']
    if not cc['vars']:
      self.vars = {}
    else:
      self.vars = cc['vars']

  def list(self):
    return self.__environment.list_templates()

  def override_loader(self, loader: jinja2.BaseLoader):
    # to make unit testing easier
    self.__environment = jinja2.Environment(loader=loader, **self._env_args)

  def render(self, script: str) -> str:
 
    template = self.__environment.from_string(script)
    content = template.render(**self.vars).strip()
    content = content[:-1] if content.endswith(';') else content
    return content
 
 