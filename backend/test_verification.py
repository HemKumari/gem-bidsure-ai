import unittest
from verification import verify
class Tests(unittest.TestCase):
 def test_threshold(self):
  r={'description':'Minimum RAM 16 GB','metric':'RAM','threshold':16,'unit':'GB'}
  self.assertEqual(verify(r,[{'name':'bid.pdf','page':1,'content':'RAM: 8 GB'}])['status'],'NON-COMPLIANT')
  self.assertEqual(verify(r,[{'name':'bid.pdf','page':1,'content':'RAM: 32 GB'}])['status'],'COMPLIANT')
  self.assertEqual(verify(r,[])['status'],'MISSING')
  self.assertEqual(verify(r,[{'name':'bid.pdf','page':1,'content':'RAM: 8 GB\nRAM: 32 GB'}])['status'],'NEEDS MANUAL REVIEW')
if __name__=='__main__':unittest.main()
