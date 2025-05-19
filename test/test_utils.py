from pprint import pprint
from unittest import TestCase

from utils import transform_dict_entries


class Test(TestCase):
    def test_transform_dict_entries(self):
        dict_list = [{"a": 1}, {"a": 2}, {"a": 3}, {"b": {"a": -1}}]
        expected = [{"A": 2}, {"A": 3}, {"A": 4}, {"b": {"A": 0}}]
        entry_filter = lambda k, v: k == "a"
        entry_transformer = lambda k, v: (k.upper(), v + 1)
        transformed = transform_dict_entries(dict_list, entry_filter, entry_transformer)
        self.assertEqual(expected, transformed)
