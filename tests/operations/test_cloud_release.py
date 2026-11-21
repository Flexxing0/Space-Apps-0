"""Software-only deployment fixtures. No scientific observations or cloud calls."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "deployment" / "cloud-run"
SPEC = importlib.util.spec_from_file_location("cloud_release_verifier", TOOLS / "verify_release.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)

FAKE_GCLOUD = r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
root=Path(os.environ['FAKE_RELEASE_ROOT'])
with (root/'calls.jsonl').open('a') as log:
    log.write(json.dumps({'tool':'gcloud','args':args})+'\n')
if args[:2]==['projects','describe']:
    print('earthlens-software-test');sys.exit(0)
if args[:3]==['run','deploy','earthlens']:
    suffix=args[args.index('--revision-suffix')+1]
    tag=args[args.index('--tag')+1]
    (root/'deployed.json').write_text(json.dumps({'revision':'earthlens-'+suffix,'tag':tag}))
    sys.exit(0)
if args[:3]==['run','services','describe']:
    traffic=[{'revisionName':'earthlens-old','percent':70},{'revisionName':'earthlens-older','percent':30}]
    state=root/'deployed.json'
    if state.exists():
        deployed=json.loads(state.read_text())
        traffic.append({'revisionName':deployed['revision'],'tag':deployed['tag'],'url':'https://preview.invalid','percent':0})
    print(json.dumps({'status':{'url':'https://public.invalid','traffic':traffic,'latestReadyRevisionName':'earthlens-old'}}))
    sys.exit(0)
if args[:3]==['run','services','update-traffic']:
    split=args[args.index('--to-revisions')+1]
    if os.environ['FAKE_SCENARIO']=='traffic_failed' and 'earthlens-old=' not in split:
        sys.exit(1)
    sys.exit(0)
raise SystemExit('Unexpected gcloud command in software test')
'''

FAKE_PYTHON = r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
if args and args[0]=='verify_release.py' and len(args)>1 and args[1].startswith('https://'):
    root=Path(os.environ['FAKE_RELEASE_ROOT'])
    with (root/'calls.jsonl').open('a') as log:
        log.write(json.dumps({'tool':'verify','url':args[1]})+'\n')
    scenario=os.environ['FAKE_SCENARIO']
    fail=(scenario=='preview_failed' and args[1]=='https://preview.invalid') or (scenario=='public_failed' and args[1]=='https://public.invalid')
    sys.exit(1 if fail else 0)
os.execv(sys.executable,[sys.executable,*args])
'''


class IntegrityTests(unittest.TestCase):
    def test_200_response_with_wrong_javascript_is_rejected(self):
        bodies = {
            '/api/health': b'{"status":"ok"}',
            '/': b'<div id="map"></div><input id="scrubber">',
            '/static/js/time-machine/workspace.js': b'old interface',
        }
        def response(request, **kwargs):
            stream = io.BytesIO(bodies[request.full_url.removeprefix('https://software.invalid')])
            stream.status = 200
            return stream
        with patch.object(verifier.urllib.request, 'urlopen', side_effect=response):
            with self.assertRaisesRegex(ValueError, 'differs'):
                verifier.verify_url('https://software.invalid', {'workspace_js_sha256':hashlib.sha256(b'new interface').hexdigest()})

    def test_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);(directory/'app').mkdir()
            source=directory/'app/app.py';source.write_bytes(b'expected code')
            (directory/'release.json').write_text(json.dumps({'files':{'app.py':hashlib.sha256(source.read_bytes()).hexdigest()}}))
            self.assertEqual(verifier.verify_files(directory)['source_files_verified'],1)
            source.write_bytes(b'changed code')
            with self.assertRaisesRegex(ValueError, 'Modified'):
                verifier.verify_files(directory)


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Requires Linux/bash; run inside Docker')
class DeploymentFlowTests(unittest.TestCase):
    def run_flow(self, scenario):
        temp=self.enterContext(tempfile.TemporaryDirectory())
        root=Path(temp);(root/'bin').mkdir();(root/'app').mkdir()
        source=root/'app/app.py';source.write_bytes(b'# software-only deployment fixture\n')
        manifest={'project_number':'224139449590','target_url':'https://target.invalid','files':{'app.py':hashlib.sha256(source.read_bytes()).hexdigest()}}
        (root/'release.json').write_text(json.dumps(manifest))
        for name in ('deploy.sh','verify_release.py'):
            shutil.copyfile(TOOLS/name,root/name)
        for name,code in (('gcloud',FAKE_GCLOUD),('python3',FAKE_PYTHON)):
            executable=root/'bin'/name
            executable.write_text('#!'+sys.executable+'\n'+code)
            executable.chmod(0o755)
        env={**os.environ,'PATH':str(root/'bin')+os.pathsep+os.environ['PATH'],'FAKE_RELEASE_ROOT':str(root),'FAKE_SCENARIO':scenario}
        result=subprocess.run(['bash',str(root/'deploy.sh')],env=env,capture_output=True,text=True,timeout=15)
        calls=[json.loads(line) for line in (root/'calls.jsonl').read_text().splitlines()]
        updates=[call for call in calls if call['tool']=='gcloud' and call['args'][:3]==['run','services','update-traffic']]
        return result,calls,updates

    def test_success_promotes_exact_tested_revision_after_preview(self):
        result,calls,updates=self.run_flow('success')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(updates),1)
        args=updates[0]['args'];split=args[args.index('--to-revisions')+1]
        self.assertTrue(split.startswith('earthlens-local-') and split.endswith('=100'))
        self.assertNotIn('LATEST',split)
        preview=next(i for i,c in enumerate(calls) if c['tool']=='verify' and c['url']=='https://preview.invalid')
        self.assertLess(preview,calls.index(updates[0]))
        self.assertEqual([c['url'] for c in calls if c['tool']=='verify'][-2:],['https://public.invalid','https://target.invalid'])

    def test_preview_failure_never_changes_public_traffic(self):
        result,_,updates=self.run_flow('preview_failed')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(updates,[])

    def test_public_failure_restores_previous_split(self):
        result,_,updates=self.run_flow('public_failed')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(len(updates),2)
        args=updates[-1]['args']
        self.assertEqual(args[args.index('--to-revisions')+1],'earthlens-old=70,earthlens-older=30')

    def test_traffic_error_attempts_restore(self):
        result,_,updates=self.run_flow('traffic_failed')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(len(updates),2)
        self.assertIn('earthlens-old=70,earthlens-older=30',updates[-1]['args'])


if __name__ == '__main__':
    unittest.main()
