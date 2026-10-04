"""Mission-orchestration simulator (IRYS Iris, EL05). Compares static, global-replan and Repair-Ladder strategies."""
import random, time, json, math, statistics as st
import numpy as np
BASE=(5,8)
TR=[]
AG=[('Scout',6,60,{'survey'}),('Inspect',5,45,{'inspect','survey'}),('Relay',5,50,set()),('Heavy',4,40,{'deliver'}),('UGV-1',2,90,{'clear','inspect'}),('UGV-2',2,90,{'survey','deliver'})]
d=lambda a,b:math.hypot(a[0]-b[0],a[1]-b[1])
def mk(rng):
    ag=[dict(n=n,sp=s,pos=BASE,free=0.0,en=e,caps=c,q=[],comm=0.0,val=0.0) for n,s,e,c in AG]
    ts=[];k=0
    for ty,cnt in(('survey',8),('inspect',4),('deliver',5),('clear',5)):
        for _ in range(cnt):
            ts.append(dict(id=k,ty=ty,pos=(rng.uniform(10,95),rng.uniform(5,55)),dur=rng.uniform(2,5),v=rng.uniform(5,10),dl=rng.uniform(30,60)));k+=1
    ev=sorted([(rng.uniform(5,25),'block',rng.randrange(6)),(rng.uniform(5,25),'comms',rng.randrange(6)),(rng.uniform(5,25),'battery',rng.choice([0,1,3])),(rng.uniform(8,25),'priority',dict(id=99,ty=rng.choice(['survey','deliver','inspect']),pos=(rng.uniform(10,95),rng.uniform(5,55)),dur=3,v=30))],key=lambda e:e[0])
    return ag,ts,ev
def run_q(a,tasks,commit_until,t0=None):
    """execute a's queue; tasks starting before commit_until are committed"""
    while a['q']:
        t=a['q'][0];tr=d(a['pos'],t['pos'])/a['sp'];s=a['free'];f=s+tr+t['dur']
        if s>=commit_until:break
        a['q'].pop(0)
        if a['en']<tr+t['dur']+d(t['pos'],BASE)/a['sp']:a['q']=[];break
        TR.append((a['n'],a['pos'],t['pos'],f<=t['dl'],t['id']))
        a['pos']=t['pos'];a['free']=f;a['en']-=tr+t['dur']
        if f<=t['dl']:a['val']+=t['v']
def tail(a):
    b=dict(a,q=[]);b['q']=[];pos,free,en=a['pos'],a['free'],a['en']
    for t in a['q']:
        tr=d(pos,t['pos'])/a['sp'];pos=t['pos'];free+=tr+t['dur'];en-=tr+t['dur']
    return pos,free,en
def alloc(pool,agents,noise=0,r=None):
    pool=list(pool);st_={id(a):tail(a) for a in agents}
    while pool:
        best=None
        for a in agents:
            pos,free,en=st_[id(a)]
            for t in pool:
                if t['ty'] not in a['caps']:continue
                tr=d(pos,t['pos'])/a['sp'];f=free+tr+t['dur']
                if f>t['dl'] or en<tr+t['dur']+d(t['pos'],BASE)/a['sp']:continue
                sc=t['v']/(f-free)*(1+noise*r.random() if noise else 1)
                if not best or sc>best[0]:best=(sc,a,t,f,tr)
        if not best:break
        _,a,t,f,tr=best;pos,free,en=st_[id(a)];st_[id(a)]=(t['pos'],f,en-tr-t['dur']);a['q'].append(t);pool.remove(t)
    return pool
def owner(ag):return {t['id']:i for i,a in enumerate(ag) for t in a['q']}
def run(strat,seed,skip=()):
    rng=random.Random(seed);ag,ts,ev=mk(rng);alloc(ts,ag);return execute(strat,ag,ts,ev,skip)
def execute(strat,ag,ts,ev,skip=(),log=None):
    lat=[];churn=0;rng=random.Random(5)
    base=sum(t['v'] for a in ag for t in a['q'])
    aware=strat in('ours','noladder');ladder=strat in('ours','nocomms')
    for idx,(te,ty,i) in enumerate(ev):
        for a in ag:run_q(a,ts,te)
        ta=time.perf_counter();old=owner(ag)
        if ty=='block':ag[i]['free']=max(ag[i]['free'],te)+6
        if ty=='comms':ag[i]['comm']=te+(3 if aware else 12)
        if ty=='battery':ag[i]['en']=min(ag[i]['en'],8)
        new=None
        if ty=='priority':
            new=dict(i,dl=te+18)
        if strat!='static' and idx not in skip:
            ok=lambda a:(a['comm']<=te) if aware else True
            cand=[a for a in ag if a['caps'] and (ok(a) or not aware)]
            if ladder:   # local fix -> partial re-auction of affected tasks only
                pool=[]
                if ty=='battery':pool=ag[i]['q'];ag[i]['q']=[]
                if ty=='block':
                    pos,free,en=ag[i]['pos'],ag[i]['free'],ag[i]['en'];keep=[]
                    for t in ag[i]['q']:
                        free+=d(pos,t['pos'])/ag[i]['sp']+t['dur'];pos=t['pos']
                        (keep if free<=t['dl'] else pool).append(t)
                    ag[i]['q']=keep
                if new:pool=pool+[new]
                left=alloc(pool,cand)
                if left:   # rung 4: escalate to global replan only if local repair could not place a task
                    pool=[t for a in ag for t in a['q']]+left
                    for a in ag:a['q']=[]
                    alloc(pool,cand)
            else:        # global replan of every unstarted task
                pool=[t for a in ag for t in a['q']]+([new] if new else [])
                for a in ag:a['q']=[]
                alloc(pool,cand)
            if not aware:   # tasks sent to a comms-down agent never arrive
                for a in ag:
                    if a['comm']>te:a['q']=[t for t in a['q'] if t['id'] in old and old[t['id']]==ag.index(a)]
            nw=owner(ag);mv=sum(1 for k,v in nw.items() if k in old and old[k]!=v);churn+=mv
            if log is not None:log.append((idx,round(te,1),ty,ag[i]['n'] if ty!='priority' else '-',mv))
        lat.append((time.perf_counter()-ta)*1000)
    for a in ag:run_q(a,ts,1e9)
    return sum(a['val'] for a in ag),base,churn/4,st.mean(lat or [0])
import copy
def cvar(v,q=.25):
    v=sorted(v);k=max(1,int(len(v)*q));return sum(v[:k])/k
def hedged(seed,K=6,M=12):
    rng=random.Random(seed);ag,ts,ev=mk(rng);cands=[]
    for k in range(K):
        c=copy.deepcopy(ag);alloc(ts,c,noise=0 if k==0 else .6,r=random.Random(seed*7+k));cands.append(c)
    def score(c):
        out=[]
        for m in range(M):
            e=mk(random.Random(seed*1000+m+1))[2];out.append(execute('ours',copy.deepcopy(c),ts,e)[0])
        return cvar(out)
    best=max(cands,key=score)
    return execute('ours',copy.deepcopy(cands[0]),ts,ev)[0],execute('ours',copy.deepcopy(best),ts,ev)[0],execute('ours',copy.deepcopy(cands[0]),ts,ev)[1]
if __name__=='__main__':
    S=[('static','Static plan'),('global','Global replan\n(comms-blind)'),('nocomms','Ladder, no\ncomms-aware'),('noladder','Global replan,\ncomms-aware'),('ours','Ours: Ladder +\ncomms-aware')]
    N=200;res={}
    for k,_ in S:
        r=[run(k,s_) for s_ in range(N)];pct=[100*a/max(b,1e-9) for a,b,_,_ in r]
        res[k]=dict(val=st.mean(pct),ci=1.96*st.stdev(pct)/N**.5,p10=sorted(pct)[N//10],churn=st.mean(c for *_,c,_ in r),lat=st.mean(l for *_,l in r))
    H=[hedged(s_) for s_ in range(1000,1000+120)]
    g=[100*a/b for a,_,b in H];h=[100*c/b for _,c,b in H]
    hed=dict(g_mean=st.mean(g),h_mean=st.mean(h),g_p10=sorted(g)[len(g)//10],h_p10=sorted(h)[len(h)//10],g_min=min(g),h_min=min(h),n=len(H),ci=1.96*st.stdev([y-x for x,y in zip(g,h)])/len(H)**.5)
    # counterfactual ledger on one seed
    best=None
    for sd in range(40):
        lg=[];rng=random.Random(sd);ag,ts,ev=mk(rng);alloc(ts,ag);v,b,_,_=execute('ours',ag,ts,ev,log=lg)
        imp=[]
        for k in range(4):
            v2=run('ours',sd,skip=(k,))[0];imp.append(v-v2)
        sc=sum(1 for x in imp if x>1)
        if not best or sc>best[0]:best=(sc,sd,lg,imp,v,b)
    led=dict(seed=best[1],log=best[2],impact=best[3],val=best[4],base=best[5])
    # scaling benchmark (vectorised greedy allocation)
    def galloc(A,T,rng):
        ap=rng.uniform(0,100,(A,2));tp=rng.uniform(0,100,(T,2));free=np.zeros(A);v=rng.uniform(5,10,T);done=np.zeros(T,bool)
        for _ in range(T):
            dist=np.linalg.norm(ap[:,None]-tp[None],axis=2);f=free[:,None]+dist/4+3
            sc=np.where(done[None],-1,v[None]/(f-free[:,None]));a,t=np.unravel_index(sc.argmax(),sc.shape)
            ap[a]=tp[t];free[a]=f[a,t];done[t]=True
    sc=[]
    for A in(6,12,24,48,96,192):
        rng=np.random.default_rng(1);T=4*A;t0=time.perf_counter();galloc(A,T,rng);g=(time.perf_counter()-t0)*1000
        k=A//6;t0=time.perf_counter();galloc(6,24,rng);h=(time.perf_counter()-t0)*1000   # one 6-agent team; teams run in parallel workers
        sc.append((A,g,h))
    json.dump(dict(res=res,scale=sc,N=N,names=S,hedge=hed,ledger=led),open('results.json','w'),default=float,indent=1)
    print(hed);print(led)
    print([(a,round(g),round(h)) for a,g,h in sc])
    