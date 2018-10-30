#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sublime
from zorgtest import (
    get_active_view_text,
    get_active_view_cursor_position,
    set_active_view_cursor_position,
    set_active_view_text,
    ZorgTestCase
)


class TestMoveHeader(ZorgTestCase):
    def test_ordinary_move(self):
        set_active_view_text(
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        set_active_view_cursor_position(1, 2)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(get_active_view_cursor_position(), (1, 2))

        set_active_view_cursor_position(2, 3)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            "some stuff\n"
            "** Caption2\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n")
        self.assertEqual(get_active_view_cursor_position(), (3, 3))

        set_active_view_cursor_position(2, 3)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            "some stuff\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(get_active_view_cursor_position(), (5, 3))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            "some stuff\n"
            "** Caption2\n"
            "** Caption\n"
            "some text\n"
            "*** Other caption\n")
        self.assertEqual(get_active_view_cursor_position(), (2, 3))

    def test_edge_of_file(self):
        set_active_view_text(
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")

        set_active_view_cursor_position(1, 5)
        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(get_active_view_cursor_position(), (1, 5))

        set_active_view_cursor_position(4, 2)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "** Caption2\n")
        self.assertEqual(get_active_view_cursor_position(), (4, 2))

    def test_other_headline(self):
        set_active_view_text(
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "some other text\n"
            "*** Other caption 2\n"
            "** Caption2\n"
            "*** Other caption 3\n")

        set_active_view_cursor_position(3, 5)
        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            "** Caption\n"
            "some text\n"
            "*** Other caption\n"
            "some other text\n"
            "*** Other caption 2\n"
            "** Caption2\n"
            "*** Other caption 3\n")
        self.assertEqual(get_active_view_cursor_position(), (3, 5))

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            "** Caption\n"
            "some text\n"
            "*** Other caption 2\n"
            "*** Other caption\n"
            "some other text\n"
            "** Caption2\n"
            "*** Other caption 3\n")
        self.assertEqual(get_active_view_cursor_position(), (4, 5))

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            "** Caption\n"
            "some text\n"
            "*** Other caption 2\n"
            "*** Other caption\n"
            "some other text\n"
            "** Caption2\n"
            "*** Other caption 3\n")
        self.assertEqual(get_active_view_cursor_position(), (4, 5))

    def test_cursor_on_boundary(self):
        set_active_view_text(
            "** Caption\n"
            "** Caption2\n"
            "text\n")
        set_active_view_cursor_position(2, 1)
        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            "** Caption2\n"
            "text\n"
            "** Caption\n")
        self.assertEqual(get_active_view_cursor_position(), (1, 1))

    def test_missing_new_line_at_eof(self):
        set_active_view_text(
            "** Caption\n"
            "** Caption2\n"
            "text")
        set_active_view_cursor_position(2, 1)
        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            "** Caption2\n"
            "text\n"
            "** Caption")
        self.assertEqual(get_active_view_cursor_position(), (1, 1))

    def test_respect_folding(self):
        set_active_view_text(
            "* Caption {\n"
            "some text}\n"
            "* Caption 2\n"
            "* Caption 3 {\n"
            "text\n"
            "** subsection\n"
            "more text}")
        set_active_view_cursor_position(1, 2)
        self.view.run_command('zorg_cycle_all')
        try:
            self.assertProperFolding()
        except:
            # do not want this test to spam output
            raise RuntimeError("folding is broken")

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
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
            get_active_view_text(),
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
        set_active_view_text(
            " - List entry\n"
            " - Other list entry\n")
        set_active_view_cursor_position(1, 1)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            " - Other list entry\n"
            " - List entry\n")
        self.assertEqual(get_active_view_cursor_position(), (2, 1))

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            " - Other list entry\n"
            " - List entry\n")
        self.assertEqual(get_active_view_cursor_position(), (2, 1))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            " - List entry\n"
            " - Other list entry\n")
        self.assertEqual(get_active_view_cursor_position(), (1, 1))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            " - List entry\n"
            " - Other list entry\n")
        self.assertEqual(get_active_view_cursor_position(), (1, 1))

    def test_sublists(self):
        set_active_view_text(
            " - List entry\n"
            "  * child list entry\n"
            "  * other child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        set_active_view_cursor_position(2, 1)

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            " - List entry\n"
            "  * other child list entry\n"
            "  * child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.assertEqual(get_active_view_cursor_position(), (3, 1))

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            " - List entry\n"
            "  * other child list entry\n"
            "  * child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.assertEqual(get_active_view_cursor_position(), (3, 1))

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
            " - List entry\n"
            "  * child list entry\n"
            "  * other child list entry\n"
            " - Other list entry\n"
            "  * 333333\n")
        self.assertEqual(get_active_view_cursor_position(), (2, 1))

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_up')

        set_active_view_cursor_position(1, 1)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
            " - Other list entry\n"
            "  * 333333\n"
            " - List entry\n"
            "  * child list entry\n"
            "  * other child list entry\n")
        self.assertEqual(get_active_view_cursor_position(), (3, 1))

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_down')

    def test_text(self):
        set_active_view_text(
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
        set_active_view_cursor_position(3, 1)

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_up')

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_down')

        set_active_view_cursor_position(5, 1)
        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
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
        self.assertEqual(get_active_view_cursor_position(), (6, 1))

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_down')

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
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
        self.assertEqual(get_active_view_cursor_position(), (5, 1))

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_up')



    def test_empty_lines(self):
        set_active_view_text(
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
        set_active_view_cursor_position(4, 1)

        self.view.run_command('zorg_move_node_down')
        self.assertEqual(
            get_active_view_text(),
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
        self.assertEqual(get_active_view_cursor_position(), (6, 1))

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_down')

        self.view.run_command('zorg_move_node_up')
        self.assertEqual(
            get_active_view_text(),
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
        self.assertEqual(get_active_view_cursor_position(), (4, 1))

        with self.ensure_nothing_changes():
            self.view.run_command('zorg_move_node_up')
