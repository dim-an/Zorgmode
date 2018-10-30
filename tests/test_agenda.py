#!/usr/bin/env python3

from zorgtest import (
    set_cursor_position,
    get_active_view,
    get_active_view_cursor_position,
    get_active_view_text,
    set_active_view_text,
    ZorgTestCase,
)


class TestAgenda(ZorgTestCase):
    def test_simple_agenda(self):
        original_file_view = get_active_view()
        set_active_view_text(
            "* TODO Write agenda tests\n"  # 1
            "** TODO Open an editor\n"  # 2
            "** TODO Type tests\n"  # 3
            "** TODO Close the editor\n")  # 4
        original_file_view.run_command("zorg_todo_list", {"show_in": "new_tab"})

        agenda_view = get_active_view()
        self.assertEqual(
            get_active_view_text(),
            "#+BEGIN_AGENDA\n"  # 1
            "#+WARNING: agenda_configuration is not found\n"  # 2
            "  TODO:    TODO Write agenda tests\n"  # 3
            "  TODO:    TODO Open an editor\n"  # 4
            "  TODO:    TODO Type tests\n"  # 5
            "  TODO:    TODO Close the editor\n"  # 6
            "#+END_AGENDA\n"  # 7
        )
        set_cursor_position(agenda_view, 5, 1)
        agenda_view.run_command("zorg_agenda_goto")

        self.assertEqual(get_active_view().id(), original_file_view.id())
        self.assertEqual(get_active_view_cursor_position(), (3, 1))
