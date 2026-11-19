# SPDX-License-Identifier: AGPL-3.0-only
# Convert every extracted MTEF v5 equation and write results.jsonl
import sys,os,json,glob,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import mtef5_starmath as m
root=sys.argv[1]; out=open(sys.argv[2],'w'); c=collections.Counter()
for idx in sorted(glob.glob(os.path.join(root,'*','index.json'))):
    doc=os.path.basename(os.path.dirname(idx))
    for r in json.load(open(idx)):
        if not r.get('native'): continue
        rec=dict(doc=doc,id=r['id'],mtef=r.get('mtef'),app=r.get('appkey'),prodver=r.get('prodver'),progid=r.get('progid'))
        if r.get('mtef')!=5: rec['status']='v3'; c['v3']+=1
        else:
            try:
                sm,eq=m.convert(open(os.path.join(os.path.dirname(idx),r['id']+'.eqn'),'rb').read())
                rec.update(chars=m.expected_chars(eq),sm=sm,constructs=sorted(eq.constructs),issues=eq.issues,fonts=[f[1] for f in eq.font_defs])
                c['ok']+=1
            except Exception as e:
                rec.update(status='parse-error',err=repr(e)); c['err']+=1
        out.write(json.dumps(rec,ensure_ascii=False)+'\n')
print(c)
