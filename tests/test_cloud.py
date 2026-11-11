import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import cloud
class CloudChecks(unittest.TestCase):
 def test_pending_never_calls_provider(self):
  with patch.object(cloud.ledger,'read',return_value={'t':{'status':'pending_owner'}}),patch.object(cloud,'call') as call:
   with self.assertRaises(ValueError):cloud.run('t')
   call.assert_not_called()
 def test_success_and_failure(self):
  for failure in [False,True]:
   with tempfile.TemporaryDirectory() as d,patch.object(cloud,'ROOT',Path(d)),patch.object(cloud.ledger,'ROOT',Path(d)):
    r=Path(d);(r/'state').mkdir();(r/'reports').mkdir();(r/'state/events.jsonl').touch()
    cloud.ledger.write('state/tasks.json',{'t':{'role':'market','status':'approved','description':'Plan research'}})
    options={'base_url':'https://example.com/v1','model':'test','max_output_tokens':10,'timeout_seconds':10}
    with patch.object(cloud,'configuration',return_value=(options,'secret-key')),patch.object(cloud.subprocess,'check_output',return_value='Role context'),patch.object(cloud,'call',side_effect=ValueError('secret') if failure else None,return_value=('Draft evidence limitations',{'total_tokens':25})):
     if failure:
      with self.assertRaises(ValueError):cloud.run('t')
     else:cloud.run('t')
    t=cloud.ledger.read('state/tasks.json')['t'];self.assertEqual(t['status'],'approved' if failure else 'awaiting_owner_review')
    saved=''.join(p.read_text() for p in r.rglob('*') if p.is_file())
    self.assertNotIn('secret-key',saved)
    if not failure:self.assertTrue((r/t['report']).exists());self.assertTrue((r/'state/checkpoints/market.json').exists())
 def test_configuration_requires_https(self):
  config={'defaults':{'base_url':'http://example.com/v1','model':'x','api_key_env':'LLM_API_KEY','max_output_tokens':10},'roles':{}}
  with patch.object(cloud.ledger,'read',return_value=config),patch.dict('os.environ',{'LLM_API_KEY':'dummy'}):
   with self.assertRaises(ValueError):cloud.configuration('market')
