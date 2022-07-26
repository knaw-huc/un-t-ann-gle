from unittest import TestCase

from untanngle.annotations import force_iri_values, is_iri, resource_target


class Test(TestCase):
    def test_is_iri(self):
        self.assertEqual(is_iri("urn:bla"), True)
        self.assertEqual(is_iri("bla"), False)
        self.assertEqual(is_iri("http://example.com/id"), True)

    def test_force_iri_values(self):
        dict_in = {
            "key": "value",
            "id": "some-identifier",
            "object": {
                "id": "object-id",
                "type": "object"
            },
            "subs": [
                {"id": "http://example.com/id"},
                {"id": "urn:some-identifier"},
                {"id": "not-an-iri"}
            ]
        }
        dict_expected = {
            "key": "value",
            "id": "urn:republic:some-identifier",
            "object": {
                "id": "urn:republic:object-id",
                "type": "object"
            },
            "subs": [
                {"id": "http://example.com/id"},
                {"id": "urn:some-identifier"},
                {"id": "urn:republic:not-an-iri"}
            ]
        }
        dict_out = force_iri_values(dict_in, {"id"}, "urn:republic:")
        self.assertDictEqual(dict_expected, dict_out)

    def test_resource_target_with_char_offset(self):
        expected_target = {
            'source': '1',
            'type': 'Text',
            'selector': {
                'type': 'urn:republic:TextAnchorSelector',
                'start': 1,
                'end': 1,
                'begin_char_offset': 0,
                'end_char_offset': 12
            }
        }
        target = resource_target(resource_id="1", begin_anchor=1, end_anchor=1, begin_char_offset=0, end_char_offset=12)
        self.assertDictEqual(expected_target, target)

    def test_resource_target_without_char_offset(self):
        expected_target = {
            'source': 'urn:resource',
            'type': 'Text',
            'selector': {
                'type': 'urn:republic:TextAnchorSelector',
                'start': 1,
                'end': 12
            }
        }
        target = resource_target(resource_id="urn:resource", begin_anchor=1, end_anchor=12)
        self.assertDictEqual(expected_target, target)
