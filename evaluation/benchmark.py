"""Observed trigger-to-card timing, rules-only, with denominators and failures."""
import json
import math
from pathlib import Path
import tempfile
import uuid
from hubrecover.application.service import RecoveryService


def benchmark(repeats=30):
    results=[]
    with tempfile.TemporaryDirectory(prefix='hubrecover-timing-') as folder:
        service=RecoveryService(Path(folder)/'timing.sqlite')
        for index in range(repeats):
            run=service.create('happy')
            trigger=next(t['at'] for t in run['trace'] if t['action']=='TRIGGER_CHECK')
            card=next((t['at'] for t in run['trace'] if t['action']=='CARD_READY'),None)
            results.append(dict(repeat=index+1,run_id=run['id'],status=run['status'],seconds=None if card is None else card-trigger))
            service.command(run['id'],'stop',revision=run['revision'],key=uuid.uuid4().hex)
    times=sorted(r['seconds'] for r in results if r['seconds'] is not None)
    return dict(mode='RULES_ONLY',requested_runs=repeats,successful_cards=len(times),failed_or_handoff=repeats-len(times),
                p95_seconds=times[math.ceil(.95*len(times))-1] if times else None,
                includes='Actual local elapsed trigger-to-first-card; excludes human waiting and execution',
                model_requests=0,business_value='UNPROVEN',runs=results)

if __name__=='__main__':
    result=benchmark()
    Path('evaluation/results/benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='runs'}))
