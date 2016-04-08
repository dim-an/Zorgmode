import sublime
from unittest import TestCase

version = sublime.version()

class TestCycleTodoState(TestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()
        # make sure we have a window to work with

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

    def setText(self, string):
        self.view.run_command("append", {"characters": string})

    def getAllText(self):
        return self.view.substr(sublime.Region(0, self.view.size()))

    def test_orgmode_cycle_forward(self):
        self.setText(
            "* Caption1\n"
            " some description\n"
            "* TODO Caption2\n")
        self.view.run_command('goto_line', {'line': 1})
        self.view.run_command('zorgmode_cycle_todo_state_forward')
        self.assertEqual(
            self.getAllText(),
            "* TODO Caption1\n"
            " some description\n"
            "* TODO Caption2\n")

        self.view.run_command('zorgmode_cycle_todo_state_forward')
        self.assertEqual(
            self.getAllText(),
            "* DONE Caption1\n"
            " some description\n"
            "* TODO Caption2\n")

        self.view.run_command('zorgmode_cycle_todo_state_forward')
        self.assertEqual(
            self.getAllText(),
            "* Caption1\n"
            " some description\n"
            "* TODO Caption2\n")

        self.view.run_command('goto_line', {'line': 2})
        self.view.run_command('zorgmode_cycle_todo_state_forward')
        self.assertEqual(
            self.getAllText(),
            "* Caption1\n"
            " some description\n"
            "* TODO Caption2\n")

        self.view.run_command('goto_line', {'line': 3})
        self.view.run_command('zorgmode_cycle_todo_state_forward')
        self.assertEqual(
            self.getAllText(),
            "* Caption1\n"
            " some description\n"
            "* DONE Caption2\n")

    def test_orgmode_cycle_backward(self):
        self.setText(
            "* Caption1\n"
            " some description\n"
            "* TODO Caption2\n")
        self.view.run_command('goto_line', {'line': 1})
        self.view.run_command('zorgmode_cycle_todo_state_backward')
        self.assertEqual(
            self.getAllText(),
            "* DONE Caption1\n"
            " some description\n"
            "* TODO Caption2\n")

        self.view.run_command('zorgmode_cycle_todo_state_backward')
        self.assertEqual(
            self.getAllText(),
            "* TODO Caption1\n"
            " some description\n"
            "* TODO Caption2\n")

        self.view.run_command('zorgmode_cycle_todo_state_backward')
        self.assertEqual(
            self.getAllText(),
            "* Caption1\n"
            " some description\n"
            "* TODO Caption2\n")
