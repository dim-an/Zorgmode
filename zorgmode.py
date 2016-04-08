# -*- coding: utf-8 -*-

import re
import sublime_plugin
import sublime

def cycle_todo_state(view, edit, forward=True):
    STATUS_LIST = ['', 'TODO', 'DONE']
    if len(view.sel()) != 1:
        return
    sel, = view.sel()
    if not sel.empty():
        return

    # - получить строку в которой мы находимся
    current_line_region = view.line(sel)
    current_line_index,_ = view.rowcol(current_line_region.a)
    current_line = view.substr(current_line_region)
    match = re.search(r'^\s*(([-+*]|[*]+)\s)(\s*\w+\b\s*|\s*)?', current_line)
    if match is None:
        return

    # - понять какой таг у нас стоит и где
    spaced_status = ''
    status_start = match.end(1)
    spaced_status = match.group(3)
    status_end = match.end(3)


    # - понять какой таг у нас следующий
    try:
        status_index = STATUS_LIST.index(spaced_status.strip())
    except ValueError:
        status_index = 0
        status_end = status_start

    delta = 1 if forward else -1
    next_status = STATUS_LIST[(status_index + delta) % len(STATUS_LIST)]

    status_region = sublime.Region(
        view.text_point(current_line_index, status_start),
        view.text_point(current_line_index, status_end))

    if next_status != '':
        next_status += ' '
    view.replace(edit, status_region, next_status)

class ZorgmodeCycleTodoStateForward(sublime_plugin.TextCommand):
    def run(self, edit):
        return cycle_todo_state(self.view, edit, forward=True)

class ZorgmodeCycleTodoStateBackward(sublime_plugin.TextCommand):
    def run(self, edit):
        return cycle_todo_state(self.view, edit, forward=False)
