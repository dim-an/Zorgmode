# -*- coding: utf-8 -*-

import collections
import itertools
import re

import sublime_plugin
import sublime

MAX_HEADLINE_LEVEL = 30

class OrgmodeStructure(object):
    SectionInfo = collections.namedtuple('SectionInfo',
                                          'headline_region,headline_level,section_region,content_region')
    def __init__(self, view):
        self.view = view

    def get_section_info(self, point=None):
        view = self.view
        if point is None:
            if len(view.sel()) != 1:
                return None
            sel, = view.sel()
            if not sel.empty():
                return None
            point = sel.a
        current_line_region = view.line(point)
        current_line = view.substr(current_line_region)
        match = re.search(r'^\s*(([-+*]|[*]+)\s)(\s*\w+\b\s*|\s*)?', current_line)
        if match is None:
            return
        current_headline_region = current_line_region
        current_headline_level = get_header_level(view.substr(current_headline_region))

        next_headline_re = '^[*]{{1,{}}}\s'.format(current_headline_level)
        next_headline_region = view.find(next_headline_re, current_headline_region.b)
        section_end = next_headline_region.a
        if section_end <= current_headline_region.a:
            section_end = view.size()

        return self.SectionInfo(
            headline_region=current_headline_region,
            headline_level=current_headline_level,
            section_region=sublime.Region(current_headline_region.a, section_end),
            content_region=sublime.Region(current_headline_region.b, section_end))

    def find_all_headlines(self, min_level=1, max_level=MAX_HEADLINE_LEVEL):
        return find_all_headers(self.view, min_level=min_level, max_level=max_level)

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

def is_line_start(view, point):
    return bool(view.classify(point) & sublime.CLASS_LINE_START)

def swap_regions(view, edit, region1, region2):
    if len(view.sel()) != 1 or not view.sel()[0].empty():
        raise ValueError
    if region1.intersects(region2):
        raise ValueError
    if region1.a > region2.a:
        return swap_regions(view, edit, region2, region1)

    if not is_line_start(view, region1.a) or not is_line_start(view, region1.b):
        raise ValueError

    if not is_line_start(view, region2.a) or (not is_line_start(view, region2.b) and region2.b != view.size()):
        raise ValueError

    added_new_line = False
    if not is_line_start(view, region2.b):
        assert region2.b == view.size()
        view.insert(edit, view.size(), '\n')
        region2 = sublime.Region(region2.a, region2.b + 1)
        added_new_line = True

    # find out new cursor position
    current_cursor_position = view.sel()[0].a
    if current_cursor_position < region1.a:
        new_cursor_position = current_cursor_position
    elif region1.contains(current_cursor_position):
        # {^....}....{..}
        # {..}....{^....}
        new_cursor_position = current_cursor_position + region2.b - region1.b
    elif region1.a > current_cursor_position:
        # {..}.^..{.....}
        # {.....}.^..{..}
        new_cursor_position = current_cursor_position + region1.size() - region2.size()
    elif region2.contains(current_cursor_position):
        # {..}....{.^...}
        # {.^...}....{..}
        new_cursor_position = current_cursor_position - region2.a + region1.a
    else:
        new_cursor_position = current_cursor_position

    text1 = view.substr(region1)
    text2 = view.substr(region2)
    view.erase(edit, region2)
    view.insert(edit, region2.a, text1)
    view.erase(edit, region1)
    view.insert(edit, region1.a, text2)

    view.sel().clear()
    view.sel().add(sublime.Region(new_cursor_position))

    if added_new_line:
        view.erase(edit, sublime.Region(view.size() - 1, view.size()))


def move_current_node(view, edit, up=True):
    if len(view.sel()) != 1 or not view.sel()[0].empty():
        return
    
    orgmode_structure = OrgmodeStructure(view)
    # Найти текущую ноду
    current_section_info = orgmode_structure.get_section_info()
    current_headline_level = current_section_info.headline_level

    # Понять её уровень
    # Найти все ноды уровня нашей ноды или выше
    all_headlines = orgmode_structure.find_all_headlines(max_level=current_headline_level)

    current_headline_index = all_headlines.index(current_section_info.headline_region)

    if up:
        swap_headline_index = current_headline_index - 1
    else:
        swap_headline_index = current_headline_index + 1


    if swap_headline_index < 0 or swap_headline_index >= len(all_headlines):
        return

    # Найти предыдущую ноду (если это нода уровнем выше, огорчиться и выйти)
    swap_headline_region = all_headlines[swap_headline_index]
    if get_header_level(view.substr(swap_headline_region)) > current_headline_level:
        return

    current_section_region = current_section_info.section_region
    swap_section_region = orgmode_structure.get_section_info(point=swap_headline_region.a).section_region

    swap_regions(view, edit, current_section_region, swap_section_region)


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

class ZorgmodeMoveNodeUp(sublime_plugin.TextCommand):
    def run(self, edit):
        move_current_node(self.view, edit, up=True)

class ZorgmodeMoveNodeDown(sublime_plugin.TextCommand):
    def run(self, edit):
        move_current_node(self.view, edit, up=False)

