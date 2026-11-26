# GeM BidSure AI — milestone 1
Development foundation, not production-ready. Python 3.11+ and Node 20+.

Backend (from backend directory):
```
python -m venv .venv
# activate .venv using your OS command
pip install -r requirements.txt
```
Set JWT_SECRET_KEY to a strong random value in your shell (PowerShell: `$env:JWT_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")`). Then run `uvicorn main:app --reload`.

Frontend (separate terminal, frontend directory): `npm install` then `npm run dev`. Open http://localhost:5173. API docs: http://localhost:8000/docs.

Register with a 12-character password, sign in, create a tender, upload a text PDF and search page evidence. SQLite and local file storage persist across restarts. PostgreSQL can be selected with DATABASE_URL=postgresql+psycopg://... .

Limitations: synchronous PDF processing, keyword search only, per-user isolation rather than full RBAC, no OCR, bidder entities, AI, reports, migrations, malware scanning, production deployment or calibrated evaluation yet. Do not upload confidential procurement data. No live GeM integration. Dependencies and runtime integration have not been tested in this environment.

## Extended MVP
Select a tender, enter approved requirements, create a bidder, upload bidder PDFs and run verification. Numeric rules support min/max/eq through API; UI exposes minimum. Optional Tesseract OCR requires installed Tesseract language data. Optional LLM_API_KEY, LLM_MODEL and LLM_BASE_URL enable advisory summaries; document excerpts are sent to that provider, so use synthetic data unless authorized. Reports export PDF/XLSX. This is not production ready: synchronous processing, lexical retrieval, no issuer authentication, no formal approval workflow, no RBAC or cloud deployment. Run `python -m unittest test_verification` from backend. Frontend and full integration not tested.

## V3 deployment preparation
Includes ranked BM25 retrieval, optional local embeddings (install sentence-transformers separately), draft requirement extraction, certificate expiry screening, human review records, and audit/analytics endpoints. Five synthetic unit tests pass. No official GeM corpus or trained classifier is included. Upload only synthetic or authorized data. PostgreSQL Docker Compose configuration requires a URL-encoded password in DATABASE_URL (host `db`), POSTGRES_PASSWORD, and a random JWT_SECRET_KEY. Run `docker compose up --build`, then run the frontend locally as above. For Render use backend Dockerfile, set DATABASE_URL and JWT_SECRET_KEY, and set FRONTEND_ORIGIN to the deployed Vercel origin. On Vercel choose frontend as root and set VITE_API_URL to the deployed backend origin. No live deployment has been verified. Local embeddings are optional and not installed by default; document processing is synchronous. Uploaded original files are not durable on ephemeral cloud storage; extracted text is stored in the database. Not approved for real procurement decisions.

## Hosted deployment and classifier evaluation

The Render Blueprint uses the existing `gem-bidsure-db` instance in Singapore and generates the authentication secret. The Vercel project builds from `frontend` and needs `VITE_API_URL` set to the Render backend origin. Set `FRONTEND_ORIGIN` on Render to the production Vercel origin. Uploaded PDFs and extracted text are stored in the database.

Run `python backend/evaluate_model.py` with the backend dependencies installed to reproduce the category model evaluation against the bundled synthetic held-out split. The classifier suggests categories during draft extraction and evidence verification. Compliance findings use the existing evidence retrieval and review rules.

The supplied split contains 96 training and 48 test examples across four categories. The archived classifier achieved 100% accuracy and 1.00 macro F1. Test templates differ from training templates and reuse the same subject terms. These scores do not establish performance on real tender documents or measure the accuracy of compliance decisions.
