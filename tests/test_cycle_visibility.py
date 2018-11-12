# -*- coding: utf-8 -*-

import sublime
from zorgtest import (
    set_active_view_text,
    get_active_view_text,
    get_active_view_cursor_position,
    set_active_view_cursor_position,
    ZorgTestCase
)


class TestMoveHeader(ZorgTestCase):
    def test_folded(self):
        set_active_view_text(
            "some stuff\n"
            "** Caption{\n"
            "some text\n"
            "*** Other caption\n"
            "more text}\n"
            "** Caption 2{\n"
            "even more text\n"
            "}\n"
            "* Caption 3{\n"
            "text text text}\n"
            "** Caption 4{\n\n}"
        )
        set_active_view_cursor_position(1, 2)
        self.view.run_command('zorg_cycle_all')
        self.assert_proper_folding()

    def test_overview(self):
        set_active_view_text(
            "some stuff\n"
            "** Caption{\n"
            "some text}\n"
            "*** Other caption{\n"
            "more text}\n"
            "** Caption 2{\n"
            "even more text\n"
            "}\n"
            "* Caption 3{\n"
            "text text text}\n"
            "** Caption 4{\n\n}"
        )
        set_active_view_cursor_position(1, 2)
        self.view.run_command('zorg_cycle_all')
        self.view.run_command('zorg_cycle_all')
        self.assert_proper_folding()

    def test_overview(self):
        set_active_view_text(
            "some stuff\n"
            "** Caption{\n"
            "some text}\n"
            "*** Other caption{\n"
            "more text}\n"
            "** Caption 2{\n"
            "even more text\n"
            "}\n"
            "* Caption 3{\n"
            "text text text}\n"
            "** Caption 4{\n\n}"
        )
        set_active_view_cursor_position(1, 2)
        self.view.run_command('zorg_cycle_all')
        self.view.run_command('zorg_cycle_all')
        self.assert_proper_folding()

    def assert_proper_folding(self):
        expected_folding = []

        text = self.view.substr(sublime.Region(0, self.view.size()))

        unmatched_braces = []
        for i, c in enumerate(text):
            if c not in "{}":
                continue
            elif c == '{':
                unmatched_braces.append(i)
            elif c == '}':
                open_brace = unmatched_braces.pop()
                close_brace = i
                expected_folding.append(sublime.Region(open_brace+1, close_brace+1))
            else:
                raise AssertionError("internal error, shouldn't be reached")

        actual_folding = self.view.folded_regions()
        self.assertEqual(expected_folding, actual_folding)
