# -*- coding: utf-8 -*-

import itertools
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

def is_straight_region(region_to_fold):
    return region_to_fold.a < region_to_fold.b

def find_all_in_region(view, expr, region, *flags):
    INVALID_REGION = sublime.Region(-1, -1)
    result = []
    pos = region.a
    while True:
        match_region = view.find(expr, pos)
        if match_region == INVALID_REGION:
            break
        if not region.contains(match_region):
            break
        if match_region.a <= pos and pos != region.a:
            break
        result.append(match_region)
        pos = match_region.b
    return result

class ZorgmodeCycle(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        if len(view.sel()) != 1:
            return
        sel, = view.sel()
        if not sel.empty():
            return

        # - получить строку в которой мы находимся
        current_line_region = view.line(sel)
        current_line_index,_ = view.rowcol(current_line_region.a)
        current_line = view.substr(current_line_region)

        # убедиться, что это headline
        match = re.search(r'^([*]+)\s', current_line)
        if not match:
            return
        current_headline_level = len(match.group(1))
        next_headline_re = '^[*]{{1,{}}}\s'.format(current_headline_level)

        # найти следующий headline того же типа или высшего
        next_headline_region = view.find(next_headline_re, current_line_region.b)
        region_to_fold = sublime.Region(current_line_region.b, next_headline_region.a - 1)
        if region_to_fold.empty():
            return
        if not is_straight_region(region_to_fold):
            region_to_fold = sublime.Region(current_line_region.b, view.size())

        # свернуть 
        folded = view.fold(region_to_fold)
        if not folded:
            view.unfold(region_to_fold)

def find_all_headers(view, min_level=1, max_level=1000):
    whole_file_region = sublime.Region(0, view.size())
    return find_all_in_region(view, "^[*]{{{},{}}}\s[^\n]*$".format(min_level, max_level), whole_file_region)

def get_header_level(string):
    for i,c in enumerate(string):
        if c != '*':
            break
    return i

def get_folding_for_headers(view, header_region_list):
    prev_header_end = None
    result = []
    for header_region in itertools.chain(header_region_list, [sublime.Region(view.size() + 1, view.size() + 1)]):
        if prev_header_end is not None:
            fold_region = sublime.Region(prev_header_end, header_region.a - 1)
            assert fold_region.a <= fold_region.b
            if not fold_region.empty():
                result.append(fold_region)
        prev_header_end = header_region.b
    return result

class ZorgmodeCycleAll(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        if len(view.sel()) != 1:
            return
        sel, = view.sel()
        if not sel.empty():
            return

        all_headers = find_all_headers(view)
        if not all_headers:
            return
        # the first header we see is top header
        top_header_max_level = get_header_level(view.substr(all_headers[0]))
        top_level_headers = find_all_headers(view, max_level=top_header_max_level)
        assert top_level_headers, "top_level_headers must at least contain first header of all_headers"
        top_headers_folding = get_folding_for_headers(view, top_level_headers)
        all_headers_folding = get_folding_for_headers(view, all_headers)

        folded_regions = view.folded_regions()

        for region in folded_regions:
            view.unfold(region)

        if folded_regions == all_headers_folding:
            # unfolded region
            pass
        elif folded_regions == top_headers_folding:
            # fold all_headers_folding
            view.fold(all_headers_folding)
        else:
            # fold top_headers_folding
            view.fold(top_headers_folding)
