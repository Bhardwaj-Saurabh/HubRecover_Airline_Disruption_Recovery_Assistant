"""Run with python -m hubrecover; binds to loopback unless --host is given."""
import argparse
import uvicorn
from hubrecover.config import load_local_environment
from hubrecover.application.api import create_app

parser=argparse.ArgumentParser(description='HubRecover local synthetic prototype')
parser.add_argument('--host',default='127.0.0.1')
parser.add_argument('--port',type=int,default=8765)
parser.add_argument('--data-dir',default='.hubrecover')
args=parser.parse_args()
load_local_environment()
uvicorn.run(create_app(args.data_dir),host=args.host,port=args.port)
