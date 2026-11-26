import os, uuid, datetime
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from category_model import classify_requirement
from pydantic import BaseModel
from pwdlib import PasswordHash
import jwt, fitz
app=FastAPI(title='GeM BidSure AI')
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('FRONTEND_ORIGIN','http://localhost:5173')],allow_methods=['*'],allow_headers=['*'])
secret=os.environ['JWT_SECRET_KEY']
if len(secret)<32: raise RuntimeError('JWT_SECRET_KEY must contain at least 32 characters')
db_url=os.getenv('DATABASE_URL','sqlite:///./bidsure.db')
if db_url.startswith(('postgres://','postgresql://')):
 db_url='postgresql+psycopg://'+db_url.split('://',1)[1]
engine=create_engine(db_url,pool_pre_ping=True)
passwords=PasswordHash.recommended()

with engine.begin() as c:
 for sql in ['CREATE TABLE IF NOT EXISTS users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, password TEXT NOT NULL)', 'CREATE TABLE IF NOT EXISTS tenders (id VARCHAR(36) PRIMARY KEY, owner VARCHAR(36) NOT NULL, title TEXT NOT NULL, reference TEXT NOT NULL)', 'CREATE TABLE IF NOT EXISTS documents (id VARCHAR(36) PRIMARY KEY, tender VARCHAR(36) NOT NULL, name TEXT NOT NULL, pages INTEGER NOT NULL)', 'CREATE TABLE IF NOT EXISTS evidence (document VARCHAR(36) NOT NULL, page INTEGER NOT NULL, content TEXT NOT NULL)', 'CREATE TABLE IF NOT EXISTS document_files (document VARCHAR(36) PRIMARY KEY, content BYTEA NOT NULL)']:
  c.execute(text(sql))
class Credentials(BaseModel):
 email:str
 password:str
class Tender(BaseModel):
 title:str
 reference:str
bearer=HTTPBearer()
def user(token=Depends(bearer)):
 try: return jwt.decode(token.credentials,secret,algorithms=['HS256'])['sub']
 except jwt.InvalidTokenError: raise HTTPException(401,'Invalid token')
def owned(c,tid,uid):
 if not c.execute(text('SELECT id FROM tenders WHERE id=:id AND owner=:u'),dict(id=tid,u=uid)).first(): raise HTTPException(404,'Tender not found')
@app.get('/health')
def health():
 with engine.connect() as c: c.execute(text('SELECT 1'))
 return {'status':'ok','database':'ready','category_model':'ready'}
@app.post('/api/auth/register')
def register(v:Credentials):
 if len(v.password)<12: raise HTTPException(400,'Password must contain at least 12 characters')
 try:
  with engine.begin() as c:
   c.execute(text('INSERT INTO users VALUES (:i,:e,:p)'),dict(i=str(uuid.uuid4()),e=v.email.lower(),p=passwords.hash(v.password)))
 except IntegrityError: raise HTTPException(409,'Account exists')
 return {'registered':True}
@app.post('/api/auth/login')
def login(v:Credentials):
 with engine.connect() as c: r=c.execute(text('SELECT * FROM users WHERE email=:e'),dict(e=v.email.lower())).mappings().first()
 if not r or not passwords.verify(v.password,r['password']): raise HTTPException(401,'Invalid credentials')
 return {'access_token':jwt.encode({'sub':r['id'],'exp':datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)},secret,algorithm='HS256')}
@app.get('/api/tenders')
def tenders(uid=Depends(user)):
 with engine.connect() as c: return [dict(r) for r in c.execute(text('SELECT id,title,reference FROM tenders WHERE owner=:u'),dict(u=uid)).mappings()]
@app.post('/api/tenders')
def create(v:Tender,uid=Depends(user)):
 i=str(uuid.uuid4())
 with engine.begin() as c: c.execute(text('INSERT INTO tenders VALUES (:i,:u,:t,:r)'),dict(i=i,u=uid,t=v.title,r=v.reference))
 return {'id':i}
@app.post('/api/tenders/{tid}/documents')
def upload(tid:str,file:UploadFile=File(...),uid=Depends(user)):
 return save_document(tid,file,uid)

def save_document(tid,file,uid,bid=None):
 with engine.connect() as c:
  if bid is None: owned(c,tid,uid)
  else: check_bidder(c,tid,bid,uid)
 data=file.file.read(20*1024*1024+1)
 if len(data)>20*1024*1024: raise HTTPException(413,'Maximum 20 MB')
 if not data.startswith(b'%PDF-'): raise HTTPException(400,'Only PDF supported in this milestone')
 try:
  with fitz.open(stream=data,filetype='pdf') as pdf:
   if len(pdf)>500: raise HTTPException(400,'Maximum 500 pages')
   pages=[]
   for p in pdf:
    content=p.get_text()
    if not content.strip():
     try: content=p.get_text(textpage=p.get_textpage_ocr(language="eng",dpi=150))
     except Exception: pass
    pages.append(content)
 except HTTPException: raise
 except Exception: raise HTTPException(400,'Unreadable PDF')
 i=str(uuid.uuid4())
 with engine.begin() as c:
  c.execute(text('INSERT INTO documents VALUES (:i,:t,:n,:p)'),dict(i=i,t=tid,n=file.filename,p=len(pages)))
  c.execute(text('INSERT INTO document_files VALUES (:i,:data)'),dict(i=i,data=data))
  if bid is not None:
   c.execute(text('INSERT INTO bid_docs VALUES (:d,:b)'),dict(d=i,b=bid))
  for n,p in enumerate(pages,1): c.execute(text('INSERT INTO evidence VALUES (:i,:n,:p)'),dict(i=i,n=n,p=p))
 return {'id':i,'pages':len(pages),'pages_needing_ocr':sum(not p.strip() for p in pages)}
@app.get('/api/tenders/{tid}/documents')
def documents(tid:str,uid=Depends(user)):
 with engine.connect() as c:
  owned(c,tid,uid); return [dict(r) for r in c.execute(text('SELECT d.* FROM documents d LEFT JOIN bid_docs b ON b.document=d.id WHERE d.tender=:t AND b.document IS NULL'),dict(t=tid)).mappings()]
@app.get('/api/tenders/{tid}/search')
def search(tid:str,q:str,uid=Depends(user)):
 with engine.connect() as c:
  owned(c,tid,uid); return [dict(r) for r in c.execute(text('SELECT d.name,e.page,e.content FROM evidence e JOIN documents d ON d.id=e.document WHERE d.tender=:t AND LOWER(e.content) LIKE :q LIMIT 20'),dict(t=tid,q='%'+q.lower()+'%')).mappings()]

from verification import verify
from fastapi.responses import StreamingResponse
from io import BytesIO
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from xml.sax.saxutils import escape
with engine.begin() as c:
 for sql in ['CREATE TABLE IF NOT EXISTS bidders (id VARCHAR(36) PRIMARY KEY,tender VARCHAR(36),name TEXT)', 'CREATE TABLE IF NOT EXISTS bid_docs (document VARCHAR(36) PRIMARY KEY,bidder VARCHAR(36))','CREATE TABLE IF NOT EXISTS requirements (id VARCHAR(36) PRIMARY KEY,tender VARCHAR(36),payload TEXT)','CREATE TABLE IF NOT EXISTS findings (id VARCHAR(36) PRIMARY KEY,bidder VARCHAR(36),payload TEXT)']:
  c.execute(text(sql))
import json
class Requirement(BaseModel):
 description:str
 metric:str=''
 threshold:float|None=None
 unit:str=''
 operator:str='min'
class Bidder(BaseModel):
 name:str
@app.post('/api/tenders/{tid}/bidders')
def add_bidder(tid:str,v:Bidder,uid=Depends(user)):
 i=str(uuid.uuid4())
 with engine.begin() as c:
  owned(c,tid,uid); c.execute(text('INSERT INTO bidders VALUES (:i,:t,:n)'),dict(i=i,t=tid,n=v.name))
 return {'id':i}
@app.get('/api/tenders/{tid}/bidders')
def list_bidders(tid:str,uid=Depends(user)):
 with engine.connect() as c:
  owned(c,tid,uid);return [dict(r) for r in c.execute(text('SELECT * FROM bidders WHERE tender=:t'),dict(t=tid)).mappings()]
@app.post('/api/tenders/{tid}/requirements')
def add_requirement(tid:str,v:Requirement,uid=Depends(user)):
 if v.operator not in ('min','max','eq'):raise HTTPException(400,'Invalid operator')
 i=str(uuid.uuid4())
 with engine.begin() as c:
  owned(c,tid,uid);c.execute(text('INSERT INTO requirements VALUES (:i,:t,:p)'),dict(i=i,t=tid,p=v.model_dump_json()))
 return {'id':i}
@app.get('/api/tenders/{tid}/requirements')
def list_requirements(tid:str,uid=Depends(user)):
 with engine.connect() as c:
  owned(c,tid,uid);return [dict(id=r.id,**json.loads(r.payload)) for r in c.execute(text('SELECT * FROM requirements WHERE tender=:t'),dict(t=tid))]
def check_bidder(c,tid,bid,uid):
 owned(c,tid,uid)
 if not c.execute(text('SELECT id FROM bidders WHERE id=:b AND tender=:t'),dict(b=bid,t=tid)).first():raise HTTPException(404,'Bidder not found')
@app.post('/api/tenders/{tid}/bidders/{bid}/documents')
def bidder_upload(tid:str,bid:str,file:UploadFile=File(...),uid=Depends(user)):
 return save_document(tid,file,uid,bid)
@app.post('/api/tenders/{tid}/bidders/{bid}/verify')
def run_verification(tid:str,bid:str,uid=Depends(user)):
 with engine.connect() as c:
  check_bidder(c,tid,bid,uid);pages=[dict(r) for r in c.execute(text('SELECT d.name,e.page,e.content FROM evidence e JOIN documents d ON d.id=e.document JOIN bid_docs b ON b.document=d.id WHERE b.bidder=:b'),dict(b=bid)).mappings()]
 reqs=list_requirements(tid,uid)
 if not reqs or not pages:raise HTTPException(400,'Add requirements and bidder documents first')
 results=[dict(requirement=r['description'],category_prediction=classify_requirement(r['description']),**verify(r,pages)) for r in reqs]
 with engine.begin() as c:
  c.execute(text('DELETE FROM findings WHERE bidder=:b'),dict(b=bid))
  for r in results:c.execute(text('INSERT INTO findings VALUES (:i,:b,:p)'),dict(i=str(uuid.uuid4()),b=bid,p=json.dumps(r)))
 return results
@app.get('/api/tenders/{tid}/bidders/{bid}/findings')
def findings(tid:str,bid:str,uid=Depends(user)):
 with engine.connect() as c:
  check_bidder(c,tid,bid,uid);return [json.loads(r.payload) for r in c.execute(text('SELECT payload FROM findings WHERE bidder=:b'),dict(b=bid))]
@app.get('/api/tenders/{tid}/bidders/{bid}/report/{fmt}')
def report(tid:str,bid:str,fmt:str,uid=Depends(user)):
 rows=findings(tid,bid,uid); out=BytesIO()
 if fmt=='xlsx':
  w=Workbook();s=w.active;s.append(['Requirement','Status','Explanation','Evidence']);
  for r in rows:s.append([(' '+str(x))[:32000] for x in [r['requirement'],r['status'],r['explanation'],json.dumps(r['evidence'])]])
  w.save(out);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
 elif fmt=='pdf':
  st=getSampleStyleSheet();story=[Paragraph('GeM BidSure AI — Advisory report',st['Title']),Paragraph('Human review required. Not an award or rejection decision.',st['Normal'])]
  for r in rows:
   story.extend([Spacer(1,12),Paragraph(escape(r['requirement']),st['Heading2']),Paragraph(escape(r['status']+' — '+r['explanation']),st['Normal'])]);
   for e in r['evidence']:story.append(Paragraph(escape(e['name']+' / page '+str(e['page'])+': '+e['content'][:1500]),st['Normal']))
  SimpleDocTemplate(out).build(story);mime='application/pdf'
 else:raise HTTPException(400,'Unsupported format')
 out.seek(0);return StreamingResponse(out,media_type=mime,headers={'Content-Disposition':f'attachment; filename="compliance.{fmt}"'})

# Human-reviewed requirement drafts, expiry screening, audit history, analytics.
from extra_api import build_router
app.include_router(build_router(engine,user,owned,check_bidder))
