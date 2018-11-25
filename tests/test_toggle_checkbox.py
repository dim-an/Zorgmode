#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sublime
from zorgtest import (
    get_active_view,
    get_active_view_text,
    set_active_view_text,
    set_active_view_cursor_position,
    ZorgTestCase,
)


class TestToggleCheckbox(ZorgTestCase):
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

    def test_selection(self):
        set_active_view_text(
            "* Caption\n"  # 1
            " - [ ] checkbox 1\n"  # 2
            " - [X] checkbox 2\n"  # 3
            "   - [ ] checkbox 3\n"  # 4
            " - [] not a checkbox 4\n"  # 5
            " - [ ] will not be toggled\n"  # 6
        )

        view = get_active_view()
        sel = view.sel().clear()
        view.sel().add(
            sublime.Region(
                0,
                view.text_point(5, 0)
            )
        )
        self.view.run_command('zorg_toggle_checkbox')
        self.assertEqual(
            get_active_view_text(),
            "* Caption\n"
            " - [X] checkbox 1\n"
            " - [X] checkbox 2\n"
            "   - [X] checkbox 3\n"
            " - [] not a checkbox 4\n"
            " - [ ] will not be toggled\n"
        )
        self.view.run_command('zorg_toggle_checkbox')
        self.assertEqual(
            get_active_view_text(),
            "* Caption\n"
            " - [ ] checkbox 1\n"
            " - [ ] checkbox 2\n"
            "   - [ ] checkbox 3\n"
            " - [] not a checkbox 4\n"
            " - [ ] will not be toggled\n"
        )
