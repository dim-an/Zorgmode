#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sublime
from unittest import TestCase

class ZorgTestCase(TestCase):
    def setCursorPos(self, line, column):
        line -= 1
        column -= 1
        point = self.view.text_point(line, column)
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(point))

    def getCursorPos(self):
        if len(self.view.sel()) != 1:
            raise ValueError
        if not self.view.sel()[0].empty():
            raise ValueError
        r, c = self.view.rowcol(self.view.sel()[0].a)
        return r + 1, c + 1

    def setText(self, string):
        self.view.run_command("append", {"characters": string})
