"""Run with python -m hubrecover; binds only to loopback."""
import argparse
import uvicorn
from hubrecover.application.api import create_app

parser=argparse.ArgumentParser(description='HubRecover local synthetic prototype')
parser.add_argument('--port',type=int,default=8765)
parser.add_argument('--data-dir',default='.hubrecover')
args=parser.parse_args()
uvicorn.run(create_app(args.data_dir),host='127.0.0.1',port=args.port)
