"""Conservative draft requirement extraction; officers must approve every item."""
import re
from category_model import classify_requirement

MANDATORY = re.compile(r'\b(must|shall|required|mandatory|minimum|maximum|at least|not less than|should submit)\b', re.I)
CATEGORY = [('certificate', 'Certifications'), ('iso ', 'Certifications'), ('bis ', 'Certifications'), ('gst', 'Statutory'), ('turnover','Financial'), ('experience','Experience'), ('ram','Technical'), ('processor','Technical'), ('capacity','Technical'), ('manufacturer','Manufacturer Authorization')]
NUMERIC = re.compile(r'\b(?:minimum|at least|not less than)\s+(?:\w+\s+){0,3}?(\d+(?:\.\d+)?)\s*(GB|MB|TB|GHz|MHz|years?|%|INR|₹|units?)\b', re.I)

def extract_requirements(pages, max_items=100):
    results, seen = [], set()
    for p in pages:
        # Text-based extraction only. OCR must run before this step for scanned pages.
        for line in p.get('content','').splitlines():
            line = re.sub(r'\s+', ' ', line).strip(' \t-•')
            if not (12 <= len(line) <= 500 and MANDATORY.search(line)):
                continue
            canonical = re.sub(r'\W+', ' ', line.lower()).strip()
            if canonical in seen:
                continue
            seen.add(canonical)
            category = next((cat for word, cat in CATEGORY if word in line.lower()), 'General Eligibility')
            threshold, unit = None, ''
            match = NUMERIC.search(line)
            if match:
                threshold, unit = float(match[1]), match[2]
            results.append({'description':line,'category':category,'category_prediction':classify_requirement(line),'mandatory':True,'threshold':threshold,'unit':unit,'operator':'min','source_document':p.get('name','unknown'),'source_page':p.get('page'),'extraction_method':'rule_based_draft','review_status':'PENDING'})
            if len(results)>=max_items:
                return results
    return results
