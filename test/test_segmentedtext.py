import unittest
from unittest import TestCase

from textservice.segmentedtext import IndexedSegmentedText, SplittableSegmentedText


class TestSegmentedText(TestCase):
    def test_splittable_segmented_text_slice(self):
        a = SplittableSegmentedText()
        list = ["Lorem", "Ipsum", "dolor", "abracadabra"]
        for i in list:
            a.append(i)
        print(a)
        slice = a.slice(0, 1)
        self.assertTrue(slice == ["Lorem", "Ipsum"])
        slice = a.slice(3, 10)
        self.assertTrue(slice == ["abracadabra"])

    def test_indexed_segmented_text_slice(self):
        a = IndexedSegmentedText()
        list = ["Lorem", "Ipsum", "dolor", "abracadabra"]
        for i in list:
            a.append(i)
        print(a)
        slice = a.slice(0, 1)
        self.assertTrue(slice == ["Lorem", "Ipsum"])
        slice = a.slice(3, 10)
        self.assertTrue(slice == ["abracadabra"])


def my_fun(i: int, s: str) -> str:
    return str(i) + s


class TestMyFun(TestCase):

    def test_my_fun(self):
        r = my_fun(1, 'a')
        assert r == "1a"


if __name__ == '__main__':
    unittest.main()
