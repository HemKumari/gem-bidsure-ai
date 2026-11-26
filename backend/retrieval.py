"""Deterministic hybrid retrieval: BM25 + optional local semantic embeddings.
No external data transmission. References are drawn from the original pages.
"""
import math
import os
import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
STOPWORDS = {'and','the','shall','must','with','for','from','that','this','are','have','been','into','will','their','its','minimum','maximum','required','bidder','tender','document','documents','certificate','certificates'}

def tokens(s):
    return [t for t in TOKEN_RE.findall(str(s).lower()) if t not in STOPWORDS]

def bm25(query, pages, top_k=8):
    if not pages or not query.strip():
        return []
    q = set(tokens(query))
    docs = [tokens(p.get('content', '')) for p in pages]
    avg = sum(map(len, docs)) / len(docs) or 1
    df = Counter(t for doc in docs for t in set(doc))
    ranking = []
    for i, doc in enumerate(docs):
        counts = Counter(doc)
        score = 0.0
        for word in q:
            n = df.get(word, 0)
            idf = math.log(1 + (len(docs) - n + .5) / (n + .5))
            tf = counts.get(word, 0)
            score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * len(doc) / avg)) if tf else 0
        if score > 0:
            ranking.append((score, i))
    ranking.sort(key=lambda item: (-item[0], item[1]))
    return [dict(pages[i], retrieval_score=round(score, 4)) for score, i in ranking[:top_k]]

_semantic_model = None

def retrieve(query, pages, top_k=8):
    """Use reciprocal rank fusion if a locally configured embedding model is available.

    Disabled by default because model downloads and embedding large procurements
    should be handled by the asynchronous worker in a production architecture.
    """
    lexical = bm25(query, pages, top_k=max(top_k * 3, 16))
    if os.getenv('ENABLE_LOCAL_EMBEDDINGS', 'false').lower() != 'true' or not pages:
        return lexical[:top_k]
    try:
        global _semantic_model
        if _semantic_model is None:
            from sentence_transformers import SentenceTransformer
            _semantic_model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'))
        embeddings = _semantic_model.encode([query] + [p['content'][:4000] for p in pages], normalize_embeddings=True)
        sims = embeddings[1:] @ embeddings[0]
        semantic = sorted(range(len(pages)), key=lambda i: -float(sims[i]))[:max(top_k * 3, 16)]
        rank = {}
        for n, page in enumerate(lexical):
            key = (page.get('document', page.get('name')), page.get('page'))
            rank[key] = rank.get(key, 0) + 1 / (60 + n + 1)
        for n, idx in enumerate(semantic):
            key = (pages[idx].get('document', pages[idx].get('name')), pages[idx].get('page'))
            rank[key] = rank.get(key, 0) + 1 / (60 + n + 1)
        out = sorted(pages, key=lambda p: -rank.get((p.get('document', p.get('name')),p.get('page')), 0))
        return [dict(p, retrieval_score=round(rank.get((p.get('document', p.get('name')),p.get('page')), 0), 6)) for p in out[:top_k] if rank.get((p.get('document', p.get('name')),p.get('page')), 0)>0]
    except (ImportError, OSError, ValueError):
        return lexical[:top_k]
