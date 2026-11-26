"""Train an advisory requirement category classifier on synthetic examples stored in SQLite."""
import sqlite3,json,random
from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
import joblib
ROOT=Path(__file__).parent
categories={'technical':['RAM','processor','storage','display','battery','network throughput'],'financial':['annual turnover','net worth','solvency','revenue','audited accounts','bid security'],'certificate':['ISO certificate','BIS registration','GST registration','Udyam certificate','quality accreditation','tax registration'],'experience':['prior contracts','work orders','past performance','completed projects','client references','years of experience']}
templates=['Bidder must provide evidence of {}','Mandatory requirement: {}','Submit documentation for {}','Eligibility shall include {}','Verification of {} is required','Provide proof of {}']
with sqlite3.connect(ROOT/'training.sqlite') as db:
 db.execute('CREATE TABLE IF NOT EXISTS examples (text TEXT PRIMARY KEY, label TEXT, split TEXT)')
 for label,terms in categories.items():
  for i,t in enumerate(templates):
   for term in terms: db.execute('INSERT OR REPLACE INTO examples VALUES (?,?,?)',(t.format(term),label,'test' if i>=4 else 'train'))
 train=db.execute("SELECT text,label FROM examples WHERE split='train'").fetchall(); test=db.execute("SELECT text,label FROM examples WHERE split='test'").fetchall()
model=make_pipeline(TfidfVectorizer(ngram_range=(1,2)),LogisticRegression(max_iter=1000,random_state=42)); model.fit(*zip(*train)); pred=model.predict([x[0] for x in test]); report=classification_report([x[1] for x in test],pred,output_dict=True,zero_division=0)
joblib.dump(model,ROOT/'category_model.joblib'); (ROOT/'model_metrics.json').write_text(json.dumps({'training_rows':len(train),'test_rows':len(test),'dataset':'synthetic; held-out templates, shared terms; not independent real-world validation','metrics':report},indent=2)); print(report['accuracy'])
