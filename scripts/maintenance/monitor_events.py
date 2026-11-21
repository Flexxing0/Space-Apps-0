"""Trabajo CLI independiente. --once por scheduler; --loop sólo para desarrollo."""
import argparse
import json
import time
from app import create_app
from services.events.monitoring import MonitoringService

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true');parser.add_argument('--loop',action='store_true')
    parser.add_argument('--interval',type=int,default=3600);parser.add_argument('--force',action='store_true')
    args=parser.parse_args(argv)
    if args.once==args.loop or args.interval<60:parser.error('Elegir --once o --loop; intervalo mínimo 60 segundos.')
    app=create_app();monitor=MonitoringService(app.extensions['earthlens_events'],app.extensions['earthlens_planning'])
    while True:
        print(json.dumps(monitor.run(force=args.force)),flush=True)
        if args.once:return 0
        time.sleep(args.interval)

if __name__=='__main__':raise SystemExit(main())
