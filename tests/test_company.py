import importlib.util,json,tempfile,unittest,hashlib,zipfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('company',Path(__file__).parents[1]/'tools/company.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class Checks(unittest.TestCase):
 def test_economics(self):
  d=json.loads((c.ROOT/'examples/unit-economics.json').read_text());r=c.estimate(d)['scenarios']['base']
  self.assertEqual(r['landed_unit_cost'],9.10);self.assertEqual(r['contribution_per_unit'],4.69)
  for value in [.95,float('nan'),-1]:
   d['scenarios']['base']['ads_rate']=value
   with self.assertRaises(ValueError):c.estimate(d)
 def test_workflow_and_migration(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(c,'ROOT',Path(tmp)):
   root=Path(tmp);c.write('agents/registry.json',{'market':{}});c.write('state/tasks.json',{'t':{'role':'market','status':'pending_owner'}});(root/'reports').mkdir();(root/'reports/r.md').write_text('Evidence')
   def run(*args):
    with patch('sys.argv',['company',*args]):c.main()
   with self.assertRaises(ValueError):run('complete','t','--report','reports/r.md')
   run('approve','t','--by','owner');run('complete','t','--report','reports/r.md');self.assertEqual(c.read('state/tasks.json')['t']['status'],'awaiting_owner_review');run('review','t','--by','owner');run('checkpoint','market','Next step')
   (root/'.env').write_text('secret');c.export(root/'export.zip')
   with zipfile.ZipFile(root/'export.zip') as z:
    self.assertNotIn('.env',z.namelist());m=json.loads(z.read('migration-manifest.json'))
    for n,h in m['files'].items():self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(),h)
    self.assertIn('state/checkpoints/market.json',m['files'])
   self.assertEqual(len((root/'state/events.jsonl').read_text().splitlines()),4)
