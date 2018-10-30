#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sublime
from zorgtest import (
    get_active_view_text,
    set_active_view_text,
    set_active_view_cursor_position,
    ZorgTestCase,
)


class TestMoveUp(ZorgTestCase):
    def test_toggle_checkbox(self):
        set_active_view_text(
            "* Caption\n"
            " - [ ] checkbox\n")

        set_active_view_cursor_position(1, 1)
        self.view.run_command('zorg_toggle_checkbox')
        self.assertEqual(
            get_active_view_text(),
            "* Caption\n"
            " - [ ] checkbox\n")

        set_active_view_cursor_position(2, 1)
        self.view.run_command('zorg_toggle_checkbox')
        self.assertEqual(
            get_active_view_text(),
            "* Caption\n"
            " - [X] checkbox\n")

        set_active_view_cursor_position(2, 1)
        self.view.run_command('zorg_toggle_checkbox')
        self.assertEqual(
            get_active_view_text(),
            "* Caption\n"
            " - [ ] checkbox\n")

    def test_unordinary_cases(self):
        TEST_STRING = (
            "* [ ] Not checkbox but a headline\n"
            " * [ ] This is checkbox\n"
            " + [ ] Also checkbox\n"
            " - [] Not a checkbox\n"
            " 100500. [ ] Checkbox\n"
            " A. [ ] Checkbox\n"
            " -[] Not a checkbox\n"
            " [ ] Not a checkbox\n"
            "- [ ] Checkbox\n"
            "-[ ] Not a checkbox\n")
        set_active_view_text(TEST_STRING)

        for i in range(len(TEST_STRING.strip('\n').split('\n'))):
            set_active_view_cursor_position(i, 1)
            self.view.run_command('zorg_toggle_checkbox')

        self.assertEqual(
            get_active_view_text(),
            "* [ ] Not checkbox but a headline\n"
            " * [X] This is checkbox\n"
            " + [X] Also checkbox\n"
            " - [] Not a checkbox\n"
            " 100500. [X] Checkbox\n"
            " A. [X] Checkbox\n"
            " -[] Not a checkbox\n"
            " [ ] Not a checkbox\n"
            "- [X] Checkbox\n"
            "-[ ] Not a checkbox\n")
