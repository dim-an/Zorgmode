#!/usr/bin/env python3

import sublime_plugin


class ZorgSelfTest(sublime_plugin.WindowCommand):
    def run(self):
        sublime_plugin.reload_plugin("zorgmode")
        self.window.run_command("unit_testing", {"package": "zorgmode"})
