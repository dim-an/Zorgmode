#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tempfile

from zorgtest import (
    get_active_view_text,
    set_active_view_cursor_position,
    set_active_view_text,
    ZorgTestCase,
)


class TestArchivation(ZorgTestCase):
    def test_simple_archivation(self):
        with tempfile.NamedTemporaryFile() as tmpf:
            set_active_view_text(
                "#+ARCHIVE:{tempfile}\n"
                "* Header 1\n"
                "** Header 2\n"
                "* Header 3\n".format(tempfile=tmpf.name))
            set_active_view_cursor_position(2, 2)
            self.view.run_command("zorg_move_to_archive")

            self.assertEqual(
                get_active_view_text(),
                "#+ARCHIVE:{tempfile}\n"
                "* Header 3\n".format(tempfile=tmpf.name))

            self.assertEqual(
                tmpf.read().decode('utf-8'),
                ("\n* Header 1\n"
                 "** Header 2\n"))

    def test_subheadline_archivation(self):
        with tempfile.NamedTemporaryFile() as tmpf:
            set_active_view_text(
                "#+ARCHIVE:{tempfile}\n"
                "* Header 1\n"
                "** Header 2\n"
                "* Header 3\n".format(tempfile=tmpf.name))
            set_active_view_cursor_position(3, 2)
            self.view.run_command("zorg_move_to_archive")

            self.assertEqual(
                get_active_view_text(),
                "#+ARCHIVE:{tempfile}\n"
                "* Header 1\n"
                "* Header 3\n".format(tempfile=tmpf.name)
            )
            self.assertEqual(
                tmpf.read().decode('utf-8'),
                "\n* Header 2\n"
            )

    def test_archivation_to_nonexistent_file(self):
        set_active_view_text(
            "#+ARCHIVE:/dev/null/nonexistent_file\n"
            "* Header 1\n"
            "** Header 2\n"
            "* Header 3\n"
        )
        set_active_view_cursor_position(3, 2)
        self.view.run_command("zorg_move_to_archive", {"silent": True})
        self.assertEqual(
            get_active_view_text(),
            "#+ARCHIVE:/dev/null/nonexistent_file\n"
            "* Header 1\n"
            "** Header 2\n"
            "* Header 3\n"
        )
