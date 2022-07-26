from unittest import TestCase

from untanngle.camel_casing import to_camel_case, keys_to_camel_case


class Test(TestCase):
    def test_to_camel_case(self):
        self.assertEqual(to_camel_case("camel_case"), "camelCase")
        self.assertEqual(to_camel_case("CamelCase"), "CamelCase")
        self.assertEqual(to_camel_case("Camel_Case"), "CamelCase")

    def test_keys_to_camel_case(self):
        dict_in = {
            "hello_world": "bla",
            "objects": [
                {"key": "value", "is_good": True},
                {"key": "value2", "is_good": False}
            ],
            "nested_objects": [
                [{"key": "value3", "is_great": True}],
                [{"key": "value4", "is_great": False}]
            ],
            "owner": {
                "first_name": "Primo",
                "last_name": "Ultimo"
            },
            "sub_list": [1, 2, 3]
        }
        dict_out = {
            "helloWorld": "bla",
            'objects': [{'isGood': True, 'key': 'value'},
                        {'isGood': False, 'key': 'value2'}],
            "nestedObjects": [
                [{"key": "value3", "isGreat": True}],
                [{"key": "value4", "isGreat": False}]
            ],
            'owner': {'firstName': 'Primo', 'lastName': 'Ultimo'},
            "subList": [1, 2, 3]
        }
        self.assertDictEqual(keys_to_camel_case(dict_in), dict_out)
