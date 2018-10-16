# -*- coding: utf-8 -*-

import sublime
from zorgtest import ZorgTestCase


class TestFollowTextLink(ZorgTestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()
        # make sure we have a window to work with

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

    def test_simple_follow_link(self):
        self.setText(
            "* Header 1\n"
            "some text [[Header 1]]\n")
        #    ^0   ^5   ^10
        self.setCursorPos(2, 12)
        self.view.run_command("zorg_follow_link")
        self.assertEqual(self.getCursorPos(), (1, 1))

    def test_simple_follow_link_header_tags(self):
        self.setText(
            "some text [[Header 2]]\n"
        #    ^0   ^5   ^10
            "* Header 1\n"
            "** Header 2 :some_tag:another_tag:\n")
        self.setCursorPos(1, 12)
        self.view.run_command("zorg_follow_link")
        self.assertEqual(self.getCursorPos(), (3, 1))
        
    def test_simple_follow_link_everything(self):
        self.setText(
            "some text [[Header 2][link text]]\n"
        #    ^0   ^5   ^10  ^15  ^20
            "* Header 1\n"
            "** TODO [#c]  Header 2  :some_tag:another_tag:  \n")
        self.setCursorPos(1, 22)
        self.view.run_command("zorg_follow_link")
        self.assertEqual(self.getCursorPos(), (3, 1))

    def test_follow_link_jump_back(self):
        self.setText(
            "* Header 1\n"
            "some text [[Header 1]]\n")
        #    ^0   ^5   ^10

        self.setCursorPos(2, 12)
        self.view.run_command("zorg_follow_link")
        self.assertEqual(self.getCursorPos(), (1, 1))

        self.view.run_command("jump_back")
        self.assertEqual(self.getCursorPos(), (2, 12))

    def test_link_abbreviations(self):
        self.setText(
            "* Header 1\n"
            "some text [[hdr:1]]\n"
            "#+LINK: hdr Header %s\n")
        #    ^0   ^5   ^10

        self.setCursorPos(2, 12)
        self.view.run_command("zorg_follow_link")
        self.assertEqual(self.getCursorPos(), (1, 1))
