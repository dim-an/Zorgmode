#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tempfile

from zorgtest import ZorgTestCase

class TestArchivation(ZorgTestCase):
    def test_simple_archivation(self):
        with tempfile.NamedTemporaryFile() as tmpf:
            self.setText(
                ("#+ARCHIVE:{tempfile}\n"
                "* Header 1\n"
                "** Header 2\n"
                "* Header 3\n").format(tempfile=tmpf.name))
            self.setCursorPos(2, 2)
            self.view.run_command("zorgmode_move_to_archive")

            self.assertEqual(
                self.getAllText(),
                ("#+ARCHIVE:{tempfile}\n"
                "* Header 3\n").format(tempfile=tmpf.name))

            self.assertEqual(
                tmpf.read().decode('utf-8'),
                ("\n* Header 1\n"
                 "** Header 2\n"))


    def test_subheadline_archivation(self):
        with tempfile.NamedTemporaryFile() as tmpf:
            self.setText(
                ("#+ARCHIVE:{tempfile}\n"
                "* Header 1\n"
                "** Header 2\n"
                "* Header 3\n").format(tempfile=tmpf.name))
            self.setCursorPos(3, 2)
            self.view.run_command("zorgmode_move_to_archive")

            self.assertEqual(
                self.getAllText(),
                ("#+ARCHIVE:{tempfile}\n"
                "* Header 1\n"
                "* Header 3\n").format(tempfile=tmpf.name))
            self.assertEqual(
                tmpf.read().decode('utf-8'),
                 "\n* Header 2\n")

    def test_archivation_to_nonexisting_directory(self):
        self.setText(
            "#+ARCHIVE:/dev/null/inexistent_file\n"
            "* Header 1\n"
            "** Header 2\n"
            "* Header 3\n")
        self.setCursorPos(3, 2)
        self.view.run_command("zorgmode_move_to_archive", {"silent": True})
        self.assertEqual(
            self.getAllText(),
            ("#+ARCHIVE:/dev/null/inexistent_file\n"
            "* Header 1\n"
            "** Header 2\n"
            "* Header 3\n"))
