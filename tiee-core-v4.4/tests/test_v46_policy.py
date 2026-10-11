import importlib.util,json,os,pathlib,sys,unittest
sys.path.insert(0,'validation')
from v46_data import trace
os.environ['V46_MODEL']=str(pathlib.Path('policies/v46/model.json').resolve())
from app.v46_policy import decide,features
class PolicyTests(unittest.TestCase):
    def test_exact_rule_attribution(self):
        for row in trace(460080,2000):
            a=decide(row['event'],'A3');b=decide(row['event'],'A4')
            for k in ('decision','p_valid','expected_cost','net_ev','feature_hash','model_version'):self.assertEqual(a[k],b[k])
    def test_hidden_label_never_crosses_interface(self):
        for row in trace(460081,100):
            event=row['event'];self.assertEqual(set(event),{'id','kind','rounds','body'});self.assertEqual(set(json.loads(event['body'])),{'signal','noise','class','deadline_ms'})
            altered=dict(event,valid=row['valid'])
            with self.assertRaises(ValueError):features(altered)
    def test_mandatory_authorized_class_bypasses_ev(self):
        event=trace(460082,1)[0]['event'];b=json.loads(event['body']);b['class']='critical';b['signal']=-3;event['body']=json.dumps(b)
        self.assertEqual(decide(event,'A3','Destructive')['decision'],'ALLOW')
if __name__=='__main__':unittest.main()
