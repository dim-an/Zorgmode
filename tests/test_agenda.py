#!/usr/bin/env python3

from zorgtest import ZorgTestCase


class TestAgenda(ZorgTestCase):
    def test_simple_agenda(self):
        self.setText(
            "* TODO Write agenda tests\n"
            "** TODO Open an editor\n"
            "** TODO Type tests\n"
            "** TODO Close the editor\n")
        self.view.run_command("zorg_todo_list", {"show_in": "new_tab"})
        self.assertEqual(
            self.get_active_view_text(),
            "#+BEGIN_AGENDA\n"
            "#+WARNING: agenda_configuration is not found\n"
            "  TODO:    TODO Write agenda tests\n"
            "  TODO:    TODO Open an editor\n"
            "  TODO:    TODO Type tests\n"
            "  TODO:    TODO Close the editor\n"
            "#+END_AGENDA\n"
        )

