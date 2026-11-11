import io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import cloud
class GeminiChecks(unittest.TestCase):
 def options(self):
  return dict(provider='gemini',base_url='https://generativelanguage.googleapis.com/v1beta',model='gemini-3.5-flash-lite',api_key_env='GEMINI_API_KEY',max_output_tokens=2000,timeout_seconds=120)
 def invoke(self,result,options=None):
  response=MagicMock();response.__enter__.return_value=io.StringIO(json.dumps(result));opener=MagicMock();opener.open.return_value=response
  with patch('urllib.request.build_opener',return_value=opener):
   output=cloud.call(options or self.options(),'test-secret',[{'role':'system','content':'Rules'},{'role':'user','content':'Plan'}])
  return output,opener.open.call_args.args[0]
 def test_gemini_request_response(self):
  output,req=self.invoke({'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'private'},{'text':'Draft'}]}}],'usageMetadata':{'totalTokenCount':42}})
  self.assertEqual(output,('Draft',{'totalTokenCount':42}));self.assertTrue(req.full_url.endswith('/models/gemini-3.5-flash-lite:generateContent'));self.assertNotIn('test-secret',req.full_url)
  self.assertEqual(req.get_header('X-goog-api-key'),'test-secret');self.assertIsNone(req.get_header('Authorization'))
  body=json.loads(req.data);self.assertEqual(body['systemInstruction']['parts'][0]['text'],'Rules');self.assertEqual(body['contents'][0]['role'],'user');self.assertEqual(body['generationConfig']['maxOutputTokens'],2000);self.assertNotIn('tools',body)
 def test_reject_incomplete_blocked_empty(self):
  for result in [{'promptFeedback':{'blockReason':'SAFETY'}},{'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]},{'candidates':[{'finishReason':'STOP','content':{'parts':[]}}]}]:
   with self.subTest(result=result),self.assertRaises(ValueError):self.invoke(result)
 def test_openai_backward_compatibility(self):
  opts=self.options();opts.pop('provider');opts['base_url']='https://example.com/v1'
  output,req=self.invoke({'choices':[{'finish_reason':'stop','message':{'content':'Draft'}}],'usage':{}},opts)
  self.assertEqual(output[0],'Draft');self.assertTrue(req.full_url.endswith('/chat/completions'));self.assertEqual(req.get_header('Authorization'),'Bearer test-secret')
 def test_config_overrides_and_validation(self):
  cfg={'defaults':self.options(),'roles':{'ceo':{'model':'custom-gemini'}}}
  with patch.object(cloud.ledger,'read',return_value=cfg),patch.dict('os.environ',{'GEMINI_API_KEY':'test-secret'}):
   opts,key=cloud.configuration('ceo');self.assertEqual(opts['model'],'custom-gemini');self.assertEqual(key,'test-secret')
   for field,value in [('model','../../bad'),('provider','unknown'),('base_url','https://evil.example/v1beta'),('timeout_seconds',0)]:
    original=cfg['defaults'][field];cfg['defaults'][field]=value
    with self.assertRaises(ValueError):cloud.configuration('market')
    cfg['defaults'][field]=original
