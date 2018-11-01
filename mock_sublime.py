#!/usr/bin/env python
# -*- coding: utf-8 -*-

import bisect


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
    def __init__(self, text: str, file_name: str = None):
        self.text = text
        self._line_index = [0]
        self._file_name = file_name

        idx = None
        while idx != -1:
            idx = self.text.find("\n", self._line_index[-1])
            if idx != -1:
                self._line_index.append(idx + 1)

    def file_name(self):
        return self._file_name

    def id(self):
        return None

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

    def rowcol(self, point):
        assert point >= 0
        row_index = bisect.bisect_right(self._line_index, point) - 1
        col_index = point - self._line_index[row_index]
        return (row_index, col_index)

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
                try:
                    b = self.size()
                except:
                    print(repr(self))
                    raise
            result.append(Region(a, b - 1))
            a = b + 1
        return result
