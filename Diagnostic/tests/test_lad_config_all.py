# TODO (A big one) Make LadConfigAll class unittest-able here.
# To achieve that, we need the following:
# - Mock VM's cert/prv key files (w/ thumbprint) that's used for decrypting the extensions's protected settings
#   and for encrypting storage key/SAS token in mdsd XML file
# - Mock a complete LAD extension's handler setting (that includes protected settings and public settings).
# - Mock RunGetOutput for external command executions.
# - Mock any other things that are necessary!
# It'd be easiest to create a test VM w/ LAD enabled and copy out necessary files to here to be used for this test.
# The test VM should be destroyed immediately. A test storage account should be used and deleted immediately.

import unittest
import json


class LadConfigAllTest(unittest.TestCase):

    def setUp(selfs):
        """
        Set up a LadConfigAll object with all dependencies properly set up and injected.
        """
        pass

    def test_lad_config_all(self):
        """
        Perform basic LadConfigAll object tests, like generating various configs and validating them.
        Initially this will be mostly just exercising the API functions, not asserting much.
        """
        pass
