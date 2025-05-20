from unittest import TestCase

from utils import transform_dict_entries


class Test(TestCase):
    def test_transform_dict_entries(self):
        dict_list = [{"a": 1}, {"a": 2}, {"a": 3}, {"b": {"a": -1}}]
        expected = [{"A": 2}, {"A": 3}, {"A": 4}, {"b": {"A": 0}}]

        def entry_filter(k, v):
            return k == "a"

        def entry_transformer(k, v):
            return k.upper(), v + 1

        transformed = transform_dict_entries(dict_list, entry_filter, entry_transformer)
        self.assertEqual(expected, transformed)
