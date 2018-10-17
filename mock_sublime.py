#!/usr/bin/env python
# -*- coding: utf-8 -*-

class Region(object):
    __slots__ = ["a", "b"]
    def __init__(self, a, b):
        assert isinstance(a, int)
        assert isinstance(b, int)
        self.a = a
        self.b = b

class View(object):
    def __init__(self, text):
        self.text = text

    def size(self):
        return len(self.text)

    def sp_iter_all_line_regions(self):
        a = 0
        while a < self.size():
            b = self.text.find('\n', a)
            if b == -1:
                b = self.text.size()
            yield Region(a, b - 1)
            a = b + 1

    def substr(self, region):
        return self.text[region.a:region.b+1]


