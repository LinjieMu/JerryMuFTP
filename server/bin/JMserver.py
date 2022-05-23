import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BASE_DIR)

if __name__ == "__main__":
    from core import management

    argv_parser = management.ManagementTool(sys.argv)
    argv_parser.excute()