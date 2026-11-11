"""Portable single-owner workflow; no external action executor."""
import argparse, hashlib, json, math, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
def now(): return datetime.now(timezone.utc).isoformat()
def read(p,default=None):
 f=ROOT/p
 return json.loads(f.read_text()) if f.exists() else default
def write(p,v):
 f=ROOT/p; f.parent.mkdir(parents=True,exist_ok=True)
 t=f.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(f)
def event(kind,**data):
 with (ROOT/'state/events.jsonl').open('a') as f:f.write(json.dumps(dict(time=now(),type=kind,**data))+'\n')
def estimate(d):
 def num(v):
  v=float(v)
  if not math.isfinite(v) or v<0:raise ValueError('Inputs must be finite and nonnegative')
  return v
 price=num(d['sale_price']);units=num(d['units']);fixed=num(d['fixed_launch_cost'])
 if price<=0 or units<=0 or units!=int(units):raise ValueError('Positive price and integer units required')
 out={}
 landed_keys=['product','packaging','inspection','freight','duty_tariffs','broker_delivery']
 keys=landed_keys+['fba','placement','storage','returns_reserve','other']
 for name,source in d['scenarios'].items():
  s={k:num(source[k]) for k in keys+['referral_rate','ads_rate']}
  rate=s['referral_rate']+s['ads_rate']
  if rate>=1:raise ValueError('Combined percentage rates must be below 1')
  landed=sum(s[k] for k in landed_keys);cost=sum(s[k] for k in keys);profit=price*(1-rate)-cost
  out[name]=dict(landed_unit_cost=round(landed,2),contribution_per_unit=round(profit,2),contribution_margin=round(profit/price,4),break_even_price_before_fixed_costs=round(cost/(1-rate),2),break_even_acos_before_fixed_costs=round((price*(1-s['referral_rate'])-cost)/price,4),profit_after_fixed_at_sell_through=round(profit*units-fixed,2),inventory_plus_fixed_cash_floor=round(landed*units+fixed,2),fixed_cost_break_even_units=math.ceil(fixed/profit) if profit>0 else None)
 return dict(currency=d['currency'],estimates_only=True,cash_note='Cash floor excludes ad funding, reserves, taxes and fee timing. Prepare a cash-flow schedule.',scenarios=out)
def export(dest):
 dest=Path(dest).resolve()
 blocked={'.git','__pycache__','secrets','credentials','.aws','.codex','.agents'}
 files=[p for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink() and not set(p.relative_to(ROOT).parts)&blocked and not p.name.startswith('.env') and p.suffix not in {'.zip','.pyc','.tmp'} and p.resolve()!=dest]
 manifest=dict(schema_version=1,exported_at=now(),files={})
 with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(files):
   b=p.read_bytes();n=p.relative_to(ROOT).as_posix();manifest['files'][n]=hashlib.sha256(b).hexdigest();z.writestr(n,b)
  z.writestr('migration-manifest.json',json.dumps(manifest,indent=2))
 return str(dest)
def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True);roles=read('agents/registry.json',{})
 for name in ['init','status']:sub.add_parser(name)
 q=sub.add_parser('task');q.add_argument('role',choices=roles);q.add_argument('description')
 for name in ['approve','review']:
  q=sub.add_parser(name);q.add_argument('id');q.add_argument('--by',required=True,choices=['owner'])
 q=sub.add_parser('complete');q.add_argument('id');q.add_argument('--report',required=True)
 q=sub.add_parser('checkpoint');q.add_argument('role',choices=roles);q.add_argument('summary')
 q=sub.add_parser('context');q.add_argument('role',choices=roles)
 q=sub.add_parser('estimate');q.add_argument('input')
 q=sub.add_parser('export');q.add_argument('destination')
 a=p.parse_args();tasks=read('state/tasks.json',{})
 if a.cmd=='init':
  (ROOT/'state/checkpoints').mkdir(parents=True,exist_ok=True);(ROOT/'state/events.jsonl').touch(exist_ok=True)
  if not (ROOT/'state/tasks.json').exists():write('state/tasks.json',{})
  print('Ready. No connections or workers enabled.')
 elif a.cmd=='status':print(json.dumps(dict(company=read('company.json'),tasks=tasks),indent=2))
 elif a.cmd=='task':
  i='task-'+uuid4().hex[:12];tasks[i]=dict(role=a.role,description=a.description,status='pending_owner',created_at=now());write('state/tasks.json',tasks);event('task_created',id=i,task=tasks[i]);print(i)
 elif a.cmd in ['approve','complete','review']:
  t=tasks[a.id];expected={'approve':'pending_owner','complete':'approved','review':'awaiting_owner_review'}[a.cmd]
  if t['status']!=expected:raise ValueError('Expected status '+expected)
  if a.cmd=='complete':
   report=(ROOT/a.report).resolve()
   if not report.is_relative_to((ROOT/'reports').resolve()) or not report.is_file():raise ValueError('Report must exist inside reports/')
   t['report']=str(report.relative_to(ROOT))
  else:t[a.cmd+'_by']=a.by
  t['status']={'approve':'approved','complete':'awaiting_owner_review','review':'reviewed'}[a.cmd];t['updated_at']=now();write('state/tasks.json',tasks);event(a.cmd,id=a.id,task=t);print(t['status'])
 elif a.cmd=='checkpoint':
  v=dict(role=a.role,updated_at=now(),summary=a.summary);write('state/checkpoints/'+a.role+'.json',v);event('checkpoint',**v);print('Saved')
 elif a.cmd=='context':
  for f in ['AGENTS.md','policies/authority.md','company.json',roles[a.role]['prompt']]:print('\n--- '+f+' ---\n'+(ROOT/f).read_text())
  print('TASKS\n'+json.dumps({k:v for k,v in tasks.items() if v['role']==a.role},indent=2));print('CHECKPOINT\n'+json.dumps(read('state/checkpoints/'+a.role+'.json'),indent=2))
 elif a.cmd=='estimate':print(json.dumps(estimate(json.loads(Path(a.input).read_text())),indent=2))
 elif a.cmd=='export':print(export(a.destination))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError) as e:print('Error: '+str(e),file=sys.stderr);sys.exit(1)
