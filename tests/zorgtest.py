#!/usr/bin/env python
# -*- coding: utf-8 -*-

from contextlib import contextmanager
from unittest import TestCase

import sublime


class ZorgTestCase(TestCase):
    def setUp(self):
        self.active_views_before_test = set(v.id() for v in sublime.active_window().views())
        self.view = sublime.active_window().new_file()

    def tearDown(self):
        current_active_views = list(sublime.active_window().views())
        for view in current_active_views:
            if view.id() in self.active_views_before_test:
                continue
            view.set_scratch(True)
            view.window().focus_view(view)
            view.window().run_command("close_file")

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

    def getAllText(self):
        return self.view.substr(sublime.Region(0, self.view.size()))

    def get_active_view_text(self):
        view = sublime.active_window().active_view()
        return view.substr(sublime.Region(0, view.size()))

    @contextmanager
    def ensureNothingChanges(self):
        old_text = self.getAllText()
        old_cursor_pos = self.getCursorPos()

        yield

        self.assertEqual(self.getAllText(), old_text)
        self.assertEqual(self.getCursorPos(), old_cursor_pos)
