import sys
from argparseing import ArgParser;
from schemachangescript import schemaChangeScript;
from schemachangedeployment import schemaChangeDeployment;
from _vars import _schemachange_version;
from  JinjaTemplateProcessor import  JinjaTemplateProcessor
from commandconfig import schemachange_config;

from logging import getLogger;
logger = getLogger(__name__);
# notes
# this is the main entry point for the schemachange command line interface
# it maps to lines 852, 846-848  in cli_original

def main(argv=sys.argv):
  parser =  ArgParser()

  # The original parameters did not support subcommands. Check if a subcommand has been supplied
  # if not default to deploy to match original behaviour.
  args = argv[1:]
  if len(args) == 0 or not any(subcommand in args[0].upper() for subcommand in ["DEPLOY", "RENDER","RENDER-DEPLOYMENT-TO-FOLDER","CHECK-DEPLOYMENT-STATUS"]):
    args = ["deploy"] + args

  args = parser.parse_args(args)

  logger.info("schemachange version: %s" % _schemachange_version)
  cc = schemachange_config(args)
  command = schemaChangeDeployment(cc)
  command.execute()

if __name__ == "__main__":
  main()

