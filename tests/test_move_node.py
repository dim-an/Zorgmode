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

    def test_ordinary_move(self):
        self.setText(
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.setCursorPos(1, 2)
        self.view.run_command('zorgmode_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (1, 2))

        self.setCursorPos(2, 3)
        self.view.run_command('zorgmode_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption2\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n")
        self.assertEqual(self.getCursorPos(), (3, 3))

        self.setCursorPos(2, 3)
        self.view.run_command('zorgmode_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (5, 3))

        self.view.run_command('zorgmode_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption2\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n")
        self.assertEqual(self.getCursorPos(), (2, 3))

    def test_edge_of_file(self):
        self.setText(
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")

        self.setCursorPos(1, 5)
        self.view.run_command('zorgmode_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (1, 5))

        self.setCursorPos(4, 2)
        self.view.run_command('zorgmode_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (4, 2))

    def test_other_headline(self):
        self.setText(
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "some other text\n"
            "*** Other caption 2\n"
            "** Caption2\n"
            "*** Other caption 3\n")

        self.setCursorPos(3, 5)
        self.view.run_command('zorgmode_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "some other text\n"
            "*** Other caption 2\n"
            "** Caption2\n"
            "*** Other caption 3\n")
        self.assertEqual(self.getCursorPos(), (3, 5))

        self.view.run_command('zorgmode_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "** Caption\n"
            "some text\n"
            "*** Other caption 2\n"
            "*** Other caption\n"
            "some other text\n"
            "** Caption2\n"
            "*** Other caption 3\n")
        self.assertEqual(self.getCursorPos(), (4, 5))

        self.view.run_command('zorgmode_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "** Caption\n"
            "some text\n"
            "*** Other caption 2\n"
            "*** Other caption\n"
            "some other text\n"
            "** Caption2\n"
            "*** Other caption 3\n")
        self.assertEqual(self.getCursorPos(), (4, 5))

    def test_cursor_on_boundary(self):
        self.setText(
            "** Caption\n"
            "** Caption2\n"
            "text\n")
        self.setCursorPos(2, 1)
        self.view.run_command('zorgmode_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "** Caption2\n"
            "text\n"
            "** Caption\n")
        self.assertEqual(self.getCursorPos(), (1, 1))

    def test_missing_new_line_at_eof(self):
        self.setText(
            "** Caption\n"
            "** Caption2\n"
            "text")
        self.setCursorPos(2, 1)
        self.view.run_command('zorgmode_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "** Caption2\n"
            "text\n"
            "** Caption")
        self.assertEqual(self.getCursorPos(), (1, 1))
