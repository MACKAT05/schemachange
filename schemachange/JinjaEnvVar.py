
import jinja2
import os
from typing import Optional
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
    if env_var in os.environ:
      result = os.environ[env_var]

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

