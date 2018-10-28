#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Region(object):
    __slots__ = ["a", "b"]

    def __init__(self, a, b):
        assert isinstance(a, int)
        assert isinstance(b, int)
        self.a = a
        self.b = b

    def __str__(self):
        return "Region({}, {})".format(self.a, self.b)


class View(object):
    def __init__(self, text: str):
        self.text = text

    def size(self):
        return len(self.text)

    def sp_iter_all_line_regions(self):
        a = 0
        while a < self.size():
            b = self.text.find('\n', a)
            if b == -1:
                b = self.text.size()
            yield Region(a, b)
            a = b + 1

    def substr(self, region):
        return self.text[region.a:region.b]

    def lines(self, region):
        # TODO: интересно, как это счастье работает когда region на границе линии.
        a = self.text.rfind("\n", 0, region.a)
        if a == -1:
            a = 0
        else:
            a += 1

        result = []
        while a < region.b:
            b = self.text.find('\n', a)
            if b == -1:
                b = self.text.size()
            result.append(Region(a, b - 1))
            a = b + 1
        return result
