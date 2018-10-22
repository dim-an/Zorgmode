#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sublime
from zorgtest import ZorgTestCase

class TestMoveHeader(ZorgTestCase):
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
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (1, 2))

        self.setCursorPos(2, 3)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption2\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n")
        self.assertEqual(self.getCursorPos(), (3, 3))

        self.setCursorPos(2, 3)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (5, 3))

        self.view.run_command('zorg_move_node_up')
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
        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(self.getCursorPos(), (1, 5))

        self.setCursorPos(4, 2)
        self.view.run_command('zorg_move_node_down')
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
        self.view.run_command('zorg_move_node_up')
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

        self.view.run_command('zorg_move_node_down')
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

        self.view.run_command('zorg_move_node_down')
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
        self.view.run_command('zorg_move_node_up')
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
        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "** Caption2\n"
            "text\n"
            "** Caption")
        self.assertEqual(self.getCursorPos(), (1, 1))

    def test_respect_folding(self):
        self.setText(
            "* Caption {\n"
            "some text}\n"
            "* Caption 2\n"
            "* Caption 3 {\n"
            "text\n"
            "** subsection\n"
            "more text}")
        self.setCursorPos(1, 2)
        self.view.run_command('zorg_cycle_all')
        try:
            self.assertProperFolding()
        except:
            # do not want this test to spam output
            raise RuntimeError("folding is broken")

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "* Caption 2\n"
            "* Caption {\n"
            "some text}\n"
            "* Caption 3 {\n"
            "text\n"
            "** subsection\n"
            "more text}")
        self.assertProperFolding()

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "* Caption 2\n"
            "* Caption 3 {\n"
            "text\n"
            "** subsection\n"
            "more text}\n"
            "* Caption {\n"
            "some text}")

    def assertProperFolding(self):
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

class TestMoveListEntry(ZorgTestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

    def test_ordinary_move(self):
        self.setText(
            " - List entry\n"
            " - Other list entry\n")
        self.setCursorPos(1, 1)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            " - Other list entry\n"
            " - List entry\n")
        self.assertEqual(self.getCursorPos(), (2, 1))

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            " - Other list entry\n"
            " - List entry\n")
        self.assertEqual(self.getCursorPos(), (2, 1))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            " - Other list entry\n")
        self.assertEqual(self.getCursorPos(), (1, 1))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            " - Other list entry\n")
        self.assertEqual(self.getCursorPos(), (1, 1))

    def test_sublists(self):
        self.setText(
            " - List entry\n"
            "  * child list entry\n"
            "  * other child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.setCursorPos(2, 1)

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            "  * other child list entry\n"
            "  * child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.assertEqual(self.getCursorPos(), (3, 1))

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            "  * other child list entry\n"
            "  * child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.assertEqual(self.getCursorPos(), (3, 1))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            "  * child list entry\n"
            "  * other child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.assertEqual(self.getCursorPos(), (2, 1))

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_up')

        self.setCursorPos(1, 1)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            " - Other list entry\n"
            "  * 333333\n"
            " - List entry\n"
            "  * child list entry\n"
            "  * other child list entry\n")
        self.assertEqual(self.getCursorPos(), (3, 1))

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_down')

    def test_text(self):
        self.setText(
            " - List entry\n"
            "  1111\n"
            "  * sublst 1 child 1\n"
            "  2222\n"
            "  * sublst 2 child 1\n"
            "  * sublst 2 child 2\n"
            " - Other list entry\n"
            "  * 4444\n"
            "  3333\n"
        )
        self.setCursorPos(3, 1)

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_up')

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_down')

        self.setCursorPos(5, 1)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            "  1111\n"
            "  * sublst 1 child 1\n"
            "  2222\n"
            "  * sublst 2 child 2\n"
            "  * sublst 2 child 1\n"
            " - Other list entry\n"
            "  * 4444\n"
            "  3333\n"
        )
        self.assertEqual(self.getCursorPos(), (6, 1))

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_down')

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            " - List entry\n"
            "  1111\n"
            "  * sublst 1 child 1\n"
            "  2222\n"
            "  * sublst 2 child 1\n"
            "  * sublst 2 child 2\n"
            " - Other list entry\n"
            "  * 4444\n"
            "  3333\n"
        )
        self.assertEqual(self.getCursorPos(), (5, 1))

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_up')



    def test_empty_lines(self):
        self.setText(
            "  * 0000\n"
            "\n"
            "\n"
            "  * 1111\n"
            " \n"
            "  * 2222\n"
            " \n"
            " \n"
            " * 3333\n"
        )
        self.setCursorPos(4, 1)

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            self.getAllText(),
            "  * 0000\n"
            "\n"
            "\n"
            "  * 2222\n"
            " \n"
            "  * 1111\n"
            " \n"
            " \n"
            " * 3333\n"
        )
        self.assertEqual(self.getCursorPos(), (6, 1))

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_down')

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            self.getAllText(),
            "  * 0000\n"
            "\n"
            "\n"
            "  * 1111\n"
            " \n"
            "  * 2222\n"
            " \n"
            " \n"
            " * 3333\n"
        )
        self.assertEqual(self.getCursorPos(), (4, 1))

        with self.ensureNothingChanges():
            self.view.run_command('zorg_move_node_up')
