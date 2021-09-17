from unittest import TestCase

from annotaton_server_proxy import About


class TestAbout(TestCase):
    def test_get(self):
        g = About().get()
        print(g)
        assert g['version'] == "1.0"
