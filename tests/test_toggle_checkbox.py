#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sublime
from zorgtest import ZorgTestCase

class TestMoveUp(ZorgTestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

    def setText(self, string):
        self.view.run_command("append", {"characters": string})

    def getAllText(self):
        return self.view.substr(sublime.Region(0, self.view.size()))

    def test_toggle_checkbox(self):
        self.setText(
            "* Caption\n"
            " - [ ] checkbox\n")

        self.setCursorPos(1, 1)
        self.view.run_command('zorgmode_toggle_checkbox')
        self.assertEqual(
            self.getAllText(),
            "* Caption\n"
            " - [ ] checkbox\n")

        self.setCursorPos(2, 1)
        self.view.run_command('zorgmode_toggle_checkbox')
        self.assertEqual(
            self.getAllText(),
            "* Caption\n"
            " - [X] checkbox\n")

        self.setCursorPos(2, 1)
        self.view.run_command('zorgmode_toggle_checkbox')
        self.assertEqual(
            self.getAllText(),
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
        self.setText(TEST_STRING)

        for i in range(len(TEST_STRING.strip('\n').split('\n'))):
            self.setCursorPos(i, 1)
            self.view.run_command('zorgmode_toggle_checkbox')

        self.assertEqual(
            self.getAllText(),
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
