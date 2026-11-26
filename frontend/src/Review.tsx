import React,{useEffect,useState} from 'react';
type RequirementDraft = {
  id: string;
  description: string;
  source_document: string;
  source_page: number;
  category: string;
  category_prediction?: { category: string };
};

export default function Review({id,api,run,token,base}:any){const [b,B]=useState<any[]>([]),[bid,I]=useState(''),[name,N]=useState(''),[req,R]=useState(''),[metric,M]=useState(''),[threshold,T]=useState(''),[unit,U]=useState(''),[rs,S]=useState<any[]>([]),[results,F]=useState<any[]>([]);const [drafts, setDrafts] = useState<RequirementDraft[]>([]);
const p='/api/tenders/'+id;
async function refreshDrafts() {
  setDrafts(await api(p+'/requirement-drafts'));
}
async function extractDrafts() {
  await api(p+'/extract-requirements','POST');
  await refreshDrafts();
}
async function approveDraft(draftId: string) {
  await api(p+'/requirement-drafts/'+draftId+'/approve','POST');
  await Promise.all([refreshDrafts(), refresh()]);
}
async function refresh(){B(await api(p+'/bidders'));S(await api(p+'/requirements'))}useEffect(()=>{I('');F([]);run(() => Promise.all([refresh(), refreshDrafts()]))},[id]);const bp=p+'/bidders/'+bid;return <section><h2>Compliance workbench</h2><h3>Draft requirements</h3>
<button onClick={() => run(extractDrafts)}>Extract requirements</button>
{drafts.map(draft => <article key={draft.id}>
  <p>{draft.description}</p>
  <p>{draft.source_document} · page {draft.source_page}</p>
  <p>Suggested category: {draft.category_prediction?.category ?? draft.category}</p>
  <button onClick={() => run(() => approveDraft(draft.id))}>Approve requirement</button>
</article>)}
<h3>Approved tender requirements</h3><input placeholder="Requirement description" value={req} onChange={e=>R(e.target.value)}/><input placeholder="Metric (e.g. RAM, optional)" value={metric} onChange={e=>M(e.target.value)}/><input type="number" placeholder="Minimum threshold" value={threshold} onChange={e=>T(e.target.value)}/><input placeholder="Unit (e.g. GB)" value={unit} onChange={e=>U(e.target.value)}/><button onClick={()=>run(async()=>{await api(p+'/requirements','POST',{description:req,metric,threshold:threshold===''?null:Number(threshold),unit});R('');await refresh()})}>Add requirement</button>{rs.map(r=><p key={r.id}>{r.description}</p>)}<h3>Bidder submissions</h3><input placeholder="Bidder name" value={name} onChange={e=>N(e.target.value)}/><button onClick={()=>run(async()=>{await api(p+'/bidders','POST',{name});await refresh()})}>Add bidder</button><select value={bid} onChange={e=>{I(e.target.value);F([]);if(e.target.value)run(async()=>F(await api(p+'/bidders/'+e.target.value+'/findings')))}}><option value="">Select bidder</option>{b.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>{bid&&<><input type="file" accept=".pdf" onChange={e=>{const f=e.target.files?.[0];if(f)run(async()=>{const data=new FormData();data.append('file',f);await api(bp+'/documents','POST',data);alert('Bidder document processed')})}}/><button onClick={()=>run(async()=>F(await api(bp+'/verify','POST')))}>Run verification</button>{results.map((r,i)=><article key={i}><h3>{r.requirement}</h3><strong>{r.status}</strong>{r.category_prediction && <p>Model category: {r.category_prediction.category}</p>}<p>{r.explanation}</p>{r.evidence.map((x:any,j:number)=><details key={j}><summary>{x.name} · page {x.page}</summary><pre>{x.content}</pre></details>)}</article>)}{['pdf','xlsx'].map(fmt=><button key={fmt} onClick={()=>run(async()=>{const r=await fetch(base+bp+'/report/'+fmt,{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error('Report failed');const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download='compliance.'+fmt;a.click();URL.revokeObjectURL(u)})}>Export {fmt.toUpperCase()}</button>)}</>}</section>}
