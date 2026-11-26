"""Additional review, extraction, and audit endpoints for the BidSure MVP."""
import json
import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from requirements_ai import extract_requirements
from verification import expiry_findings


def build_router(engine, user, owned, check_bidder):
    router=APIRouter()
    with engine.begin() as c:
        for sql in [
            'CREATE TABLE IF NOT EXISTS extracted_drafts (id VARCHAR(36) PRIMARY KEY,tender VARCHAR(36) NOT NULL,payload TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS human_reviews (id VARCHAR(36) PRIMARY KEY,tender VARCHAR(36) NOT NULL,bidder VARCHAR(36) NOT NULL,requirement TEXT NOT NULL,decision TEXT NOT NULL,notes TEXT NOT NULL,reviewer VARCHAR(36) NOT NULL,created_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS audit_entries (id VARCHAR(36) PRIMARY KEY,tender VARCHAR(36) NOT NULL,actor VARCHAR(36) NOT NULL,action TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL)'
        ]:c.execute(text(sql))
    def log(c,tid,actor,action,details=''):
        c.execute(text('INSERT INTO audit_entries VALUES (:i,:t,:a,:action,:d,CURRENT_TIMESTAMP)'),{'i':str(uuid.uuid4()),'t':tid,'a':actor,'action':action,'d':details[:500]})
    class Review(BaseModel):
        requirement:str=Field(min_length=3, max_length=1000)
        decision:str
        notes:str=Field(default='',max_length=4000)
    @router.post('/api/tenders/{tid}/extract-requirements')
    def run_extraction(tid:str,uid=Depends(user)):
        with engine.begin() as c:
            owned(c,tid,uid)
            pages=[dict(r) for r in c.execute(text('SELECT d.name,e.page,e.content FROM evidence e JOIN documents d ON d.id=e.document LEFT JOIN bid_docs b ON b.document=d.id WHERE d.tender=:t AND b.document IS NULL'),{'t':tid}).mappings()]
            if not pages:raise HTTPException(400,'Upload tender PDF documents before extracting requirements')
            drafts=extract_requirements(pages)
            c.execute(text('DELETE FROM extracted_drafts WHERE tender=:t'),{'t':tid})
            for draft in drafts:
                c.execute(text('INSERT INTO extracted_drafts VALUES (:i,:t,:p)'),{'i':str(uuid.uuid4()),'t':tid,'p':json.dumps(draft)})
            log(c,tid,uid,'requirements_extracted',f'{len(drafts)} draft rules')
        return {'drafts':drafts,'total':len(drafts),'notice':'Drafts require officer review and approval before use.'}
    @router.get('/api/tenders/{tid}/requirement-drafts')
    def drafts(tid:str,uid=Depends(user)):
        with engine.connect() as c:
            owned(c,tid,uid)
            return [dict(id=r.id,**json.loads(r.payload)) for r in c.execute(text('SELECT id,payload FROM extracted_drafts WHERE tender=:t'),{'t':tid})]
    @router.post('/api/tenders/{tid}/requirement-drafts/{did}/approve')
    def approve(tid:str,did:str,uid=Depends(user)):
        with engine.begin() as c:
            owned(c,tid,uid)
            r=c.execute(text('DELETE FROM extracted_drafts WHERE id=:i AND tender=:t RETURNING payload'),{'i':did,'t':tid}).first()
            if not r:raise HTTPException(404,'Draft not found')
            p=json.loads(r.payload)
            rid=str(uuid.uuid4())
            req={'description':p['description'],'metric':'','threshold':None,'unit':'','operator':'min', 'source_document':p['source_document'],'source_page':p['source_page'],'category':p['category'],'category_prediction':p.get('category_prediction')}
            c.execute(text('INSERT INTO requirements VALUES (:i,:t,:p)'),{'i':rid,'t':tid,'p':json.dumps(req)})
            log(c,tid,uid,'requirement_approved',rid)
        return {'id':rid,'approved':True}
    @router.get('/api/tenders/{tid}/bidders/{bid}/certificate-checks')
    def certificates(tid:str,bid:str,uid=Depends(user)):
        with engine.connect() as c:
            check_bidder(c,tid,bid,uid)
            pages=[dict(r) for r in c.execute(text('SELECT d.name,e.page,e.content FROM evidence e JOIN documents d ON d.id=e.document JOIN bid_docs b ON b.document=d.id WHERE b.bidder=:b'),{'b':bid}).mappings()]
        return {'findings':expiry_findings(pages),'note':'Dates are extracted from submitted documents; issuing-authority authenticity is NOT verified.'}
    @router.post('/api/tenders/{tid}/bidders/{bid}/reviews')
    def review(tid:str,bid:str,v:Review,uid=Depends(user)):
        if v.decision not in ('APPROVED','REJECTED','NEEDS_CLARIFICATION'):
            raise HTTPException(400,'Invalid review decision')
        with engine.begin() as c:
            check_bidder(c,tid,bid,uid)
            # Ensure that the requirement was evaluated for this bidder.
            findings=[json.loads(r.payload) for r in c.execute(text('SELECT payload FROM findings WHERE bidder=:b'),{'b':bid})]
            if v.requirement not in [r['requirement'] for r in findings]:raise HTTPException(400,'Requirement not in verification findings')
            rid=str(uuid.uuid4())
            c.execute(text('INSERT INTO human_reviews VALUES (:i,:t,:b,:r,:d,:n,:u,CURRENT_TIMESTAMP)'),{'i':rid,'t':tid,'b':bid,'r':v.requirement,'d':v.decision,'n':v.notes,'u':uid})
            log(c,tid,uid,'human_review_recorded',rid)
        return {'id':rid,'recorded':True,'disclaimer':'Human review record; not an automated tender award or rejection.'}
    @router.get('/api/tenders/{tid}/bidders/{bid}/reviews')
    def reviews(tid:str,bid:str,uid=Depends(user)):
        with engine.connect() as c:
            check_bidder(c,tid,bid,uid)
            return [dict(r) for r in c.execute(text('SELECT id,requirement,decision,notes,reviewer,created_at FROM human_reviews WHERE tender=:t AND bidder=:b ORDER BY created_at DESC'),{'t':tid,'b':bid}).mappings()]
    @router.get('/api/tenders/{tid}/audit-logs')
    def audit(tid:str,uid=Depends(user)):
        with engine.connect() as c:
            owned(c,tid,uid)
            return [dict(r) for r in c.execute(text('SELECT action,details,created_at FROM audit_entries WHERE tender=:t ORDER BY created_at DESC LIMIT 100'),{'t':tid}).mappings()]
    @router.get('/api/tenders/{tid}/analytics')
    def analytics(tid:str,uid=Depends(user)):
        with engine.connect() as c:
            owned(c,tid,uid)
            bidders=c.execute(text('SELECT COUNT(*) FROM bidders WHERE tender=:t'),{'t':tid}).scalar_one()
            reqs=c.execute(text('SELECT COUNT(*) FROM requirements WHERE tender=:t'),{'t':tid}).scalar_one()
            findings=[]
            for r in c.execute(text('SELECT f.payload FROM findings f JOIN bidders b ON b.id=f.bidder WHERE b.tender=:t'),{'t':tid}):findings.append(json.loads(r.payload))
            statuses={}
            for f in findings:statuses[f['status']]=statuses.get(f['status'],0)+1
            return {'bidders':bidders,'requirements':reqs,'findings':len(findings),'status_counts':statuses}
    return router
