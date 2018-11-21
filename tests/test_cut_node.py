# -*- coding: utf-8 -*-

from zorgtest import (
    get_active_view,
    get_active_view_text,
    set_active_view_cursor_position,
    set_active_view_text,
    ZorgTestCase,
)


class TestCutNode(ZorgTestCase):
    def test_cut_section(self):
        set_active_view_text(
            "* Header 1\n"
            "some text\n"
            "** Header 2\n"
            "another text\n"
            "* Header 3\n"
        )
        set_active_view_cursor_position(1, 1)
        get_active_view().run_command("zorg_cut_node")
        self.assertEqual(
            get_active_view_text(),
            "* Header 3\n"
        )

    def test_cut_list_entry(self):
        set_active_view_text(
            "  - foo\n"
            "  - bar\n"
            "    * baz\n"
            "     continuation of baz\n"
            "   continuation of bar\n"
            " + qux\n"
        )
        set_active_view_cursor_position(2, 1)
        get_active_view().run_command("zorg_cut_node")
        self.assertEqual(
            get_active_view_text(),
            "  - foo\n"
            " + qux\n"
        )

    def test_cut_section_with_example(self):
        set_active_view_text(
            "* Header 1\n"
            "* Header 2\n"
            "#+BEGIN_EXAMPLE\n"
            "* This is actually not a header\n"
            "#+END_EXAMPLE\n"
            " #+BEGIN_EXAMPLE\n"
            "* This is also not a header\n"
            " #+END_EXAMPLE \n"
            "* Header 3\n"

        )
        set_active_view_cursor_position(2, 1)
        get_active_view().run_command("zorg_cut_node")
        self.assertEqual(
            get_active_view_text(),
            "* Header 1\n"
            "* Header 3\n"
        )

    def test_cut_section_with_src(self):
        set_active_view_text(
            "* Header 1\n"
            "* Header 2\n"
            "#+BEGIN_SRC\n"
            "* This is actually not a header\n"
            "#+END_SRC\n"
            " #+BEGIN_SRC\n"
            "* This is also not a header\n"
            " #+END_SRC \n"
            "* Header 3\n"

        )
        set_active_view_cursor_position(2, 1)
        get_active_view().run_command("zorg_cut_node")
        self.assertEqual(
            get_active_view_text(),
            "* Header 1\n"
            "* Header 3\n"
        )
