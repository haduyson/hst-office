# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Minimal read-only Compound File Binary reader (stdlib only).
import struct
class CFB:
    def __init__(s,data):
        s.d=data; assert data[:8]==b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        s.ss=1<<struct.unpack_from('<H',data,30)[0]; s.mss=1<<struct.unpack_from('<H',data,32)[0]
        nfat,dir0,_,s.cutoff,mini0,nmini,difat0,ndifat=struct.unpack_from('<IIIIIIII',data,44)
        difat=list(struct.unpack_from('<109I',data,76)); sec=difat0
        for _ in range(ndifat):
            if sec>=0xfffffffa: break
            v=struct.unpack_from('<%dI'%(s.ss//4),s.sec(sec)); difat+=v[:-1]; sec=v[-1]
        s.fat=[]
        for f in difat[:nfat]: s.fat+=struct.unpack_from('<%dI'%(s.ss//4),s.sec(f))
        dd=s.chain(dir0); s.ents=[]
        for i in range(0,len(dd),128):
            e=dd[i:i+128]; nl=struct.unpack_from('<H',e,64)[0]
            name=e[:max(nl-2,0)].decode('utf-16le','replace')
            typ=e[66]; l,r,c=struct.unpack_from('<III',e,68); st,sz=struct.unpack_from('<IQ',e,116)
            s.ents.append(dict(name=name,type=typ,l=l,r=r,c=c,start=st,size=sz&0xffffffff,clsid=e[80:96]))
        root=s.ents[0]; s.ministream=s.chain(root['start'])[:root['size']]
        s.minifat=[]
        if nmini: md=s.chain(mini0); s.minifat=list(struct.unpack_from('<%dI'%(len(md)//4),md))
    def sec(s,n): o=(n+1)*s.ss; return s.d[o:o+s.ss]
    def chain(s,st):
        out=[];n=st;seen=0
        while n<0xfffffffa and seen<10**6: out.append(s.sec(n)); n=s.fat[n]; seen+=1
        return b''.join(out)
    def read(s,e):
        if e['size']<s.cutoff and e['type']==2:
            out=[];n=e['start']
            while n<0xfffffffa: o=n*s.mss; out.append(s.ministream[o:o+s.mss]); n=s.minifat[n]
            return b''.join(out)[:e['size']]
        return s.chain(e['start'])[:e['size']]
    def children(s,idx):
        res={}; st=[s.ents[idx]['c']]
        while st:
            i=st.pop()
            if i==0xffffffff or i>=len(s.ents): continue
            e=s.ents[i]; res[e['name']]=i; st+= [e['l'],e['r']]
        return res
    def find(s,path):
        i=0
        for p in path:
            ch=s.children(i)
            if p not in ch: return None
            i=ch[p]
        return i
