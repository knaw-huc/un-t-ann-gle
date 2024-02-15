import unittest

from textrepo.client import TextRepoClient

import textfabric as tf
from utils import trc_has_document_with_external_id


class MyTestCase(unittest.TestCase):
    def test_get_file_num(self):
        self.assertEqual(tf.get_file_num("data/text-1.json"), "1")  # add assertion here
        self.assertEqual(tf.get_file_num("annot-10.json"), "10")  # add assertion here
        self.assertEqual(tf.get_file_num("annotations.json"), None)  # add assertion here

    def test_trc_has_document_with_external_id(self):
        trc = TextRepoClient("https://suriano.tt.di.huc.knaw.nl/textrepo", verbose=True)
        exists = trc_has_document_with_external_id(trc, "suriano")
        self.assertEqual(exists, True)
        does_not_exist = trc_has_document_with_external_id(trc, "blablabla")
        self.assertEqual(does_not_exist, False)


if __name__ == '__main__':
    unittest.main()
