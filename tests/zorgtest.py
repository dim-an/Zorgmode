#!/usr/bin/env python
# -*- coding: utf-8 -*-

from contextlib import contextmanager
from unittest import TestCase

import sublime


def get_active_view():
    return sublime.active_window().active_view()


def get_active_view_text():
    view = get_active_view()
    return view.substr(sublime.Region(0, view.size()))


def get_active_view_cursor_position():
    view = get_active_view()

    sel = view.sel()
    if len(sel) == 0:
        raise ValueError("Empty selection")

    if len(view.sel()) > 1:
        raise ValueError("Multiple selection")

    if not view.sel()[0].empty():
        raise ValueError("Nonempty selection")

    r, c = view.rowcol(view.sel()[0].a)
    return r + 1, c + 1


def set_cursor_position(view, line, column):
    line -= 1
    column -= 1
    point = view.text_point(line, column)
    view.sel().clear()
    view.sel().add(sublime.Region(point))


def set_active_view_cursor_position(line, column):
    view = get_active_view()
    set_cursor_position(view, line, column)


def set_active_view_text(string):
    view = get_active_view()
    view.run_command("append", {"characters": string})


class ZorgTestCase(TestCase):
    def setUp(self):
        self.active_views_before_test = set(v.id() for v in sublime.active_window().views())
        self.view = sublime.active_window().new_file()
        self.maxDiff = None

    def tearDown(self):
        current_active_views = list(sublime.active_window().views())
        for view in current_active_views:
            if view.id() in self.active_views_before_test:
                continue
            view.set_scratch(True)
            view.window().focus_view(view)
            view.window().run_command("close_file")

    @contextmanager
    def ensure_nothing_changes(self):
        old_view_id = get_active_view().id
        old_text = get_active_view_text()
        old_cursor_pos = get_active_view_cursor_position()

        yield

        self.assertEqual(get_active_view().id, old_view_id)
        self.assertEqual(get_active_view_text(), old_text)
        self.assertEqual(get_active_view_cursor_position(), old_cursor_pos)
