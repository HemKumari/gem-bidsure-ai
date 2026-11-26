import unittest
from datetime import date
from retrieval import bm25, retrieve
from requirements_ai import extract_requirements
from verification import expiry_findings, verify

class IntelligenceTests(unittest.TestCase):
    def test_bm25_evidence_provenance(self):
        pages=[{'name':'a.pdf','page':1,'content':'irrelevant office text'}, {'name':'b.pdf','page':17,'content':'RAM: 8 GB is installed on the offered computer'}]
        found=bm25('RAM 16 GB',pages)
        self.assertTrue(found)
        self.assertEqual((found[0]['name'], found[0]['page']),('b.pdf',17))
    def test_requirements_are_drafts_not_approved(self):
        pages=[{'name':'tender.pdf','page':4,'content':'The bidder must submit a valid GST certificate.\nMinimum RAM required is at least 16 GB.'}]
        drafts=extract_requirements(pages)
        self.assertEqual(len(drafts),2)
        self.assertTrue(all(r['review_status']=='PENDING' for r in drafts))
        self.assertEqual(drafts[0]['source_page'],4)
    def test_expiry_is_not_authentication(self):
        pages=[{'name':'iso.pdf','page':5,'content':'Expiry date: 01/01/2025'}]
        result=expiry_findings(pages,date(2026,11,26))
        self.assertEqual(result[0]['status'],'EXPIRED')
        self.assertEqual(result[0]['authenticity'],'NOT_VERIFIED')
    def test_missing_vs_non_compliance(self):
        r={'description':'Minimum RAM 16 GB','metric':'RAM','threshold':16,'unit':'GB'}
        self.assertEqual(verify(r,[])['status'],'MISSING')
        self.assertEqual(verify(r,[{'name':'spec.pdf','page':1,'content':'RAM: 8 GB'}])['status'],'NON-COMPLIANT')

if __name__=='__main__':unittest.main()
