import unittest
import workloadPatch.WorkloadPatch as wp

class TestWP(unittest.TestCase):
    def test_preMaster(self):
        self.assertEquals(wp.preMaster(), None)

if __name__ == '__main__':
    unittest.main()