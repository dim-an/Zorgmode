# -*- coding: utf-8 -*-

import webbrowser
import collections
import itertools
import os
import re
import subprocess

import sublime_plugin
import sublime

from . import zorg_parse

try:
    import Default.history_list as history_list_plugin
except ImportError:
    history_list_plugin = None

MAX_HEADLINE_LEVEL = 30

OrgLinkInfo = collections.namedtuple("OrgLinkInfo", "start,end,reference,text")

if history_list_plugin:
    def save_position_for_jump_history(view):
        jump_history = history_list_plugin.get_jump_history_for_view(view)
        jump_history.push_selection(view)
else:
    def save_position_for_jump_history(view):
        pass

def goto(view, point):
    save_position_for_jump_history(view)
    view.sel().clear()
    view.sel().add(sublime.Region(point))
    view.show(point)

def zorg_parse_document(view):
    return zorg_parse.parse_org_string(view.substr(sublime.Region(0, view.size())))

def find_links_in_string(text):
    processed_end = 0
    link_list = []
    while True:
        start_marker = text.find("[[", processed_end)
        if start_marker == -1:
            return link_list
        end_marker = text.find("]]", start_marker)
        if end_marker == -1:
            return link_list
        separation_marker = text.find("][", start_marker, end_marker)
        if separation_marker == -1:
            link_text = None
            link_reference = text[start_marker + 2:end_marker]
        else:
            link_text = text[separation_marker + 2:end_marker]
            link_reference = text[start_marker + 2:separation_marker]
        link_list.append(OrgLinkInfo(
            start=start_marker,
            end=end_marker + 2,
            reference=link_reference,
            text=link_text))
        processed_end = end_marker + 2

class OrgmodeStructure(object):
    SectionInfo = collections.namedtuple('SectionInfo',
                                         'headline_region,headline_level,section_region,content_region')
    def __init__(self, view):
        self.view = view

    def get_cursor_point(self):
        view = self.view
        if len(view.sel()) != 1:
            return None
        sel, = view.sel()
        if not sel.empty():
            return None
        return sel.a

    def get_line_region(self, point=None):
        view = self.view
        if point is None:
            if len(view.sel()) != 1:
                return None
            sel, = view.sel()
            if not sel.empty():
                return None
            point = sel.a
        return view.line(point)

    def get_section_info(self, point=None):
        view = self.view
        current_line_region = self.get_line_region(point=point)
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

    # TODO: переименовать special_lines в control_lines
    def iter_special_lines(self, line_tag):
        if not re.match("^[A-Za-z0-9_]*$", line_tag):
            raise ValueError("Bad line tag: {}".format(line_tag))

        regexp = "^#[+]{}: *(.*) *$".format(line_tag)
        text = self.view.substr(sublime.Region(0, self.view.size()))
        for match in re.finditer(regexp, text, flags=re.MULTILINE):
            yield match.group(1)

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

class ZorgCycleTodoStateForward(sublime_plugin.TextCommand):
    def run(self, edit):
        return cycle_todo_state(self.view, edit, forward=True)

class ZorgCycleTodoStateBackward(sublime_plugin.TextCommand):
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

class ZorgCycle(sublime_plugin.TextCommand):
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

def strictly_within(region1, region2):
    return region2.a < region1.a <= region1.b < region2.b

def project_point_after_swapping(region1, region2, point):
    # NOTE: there is a tricky case when region1.b == region2.a
    # In that case point moves with region2.

    assert not region1.intersects(region2)
    assert region1.b <= region2.a

    # find out new cursor position
    if point < region1.a:
        return point
    elif region2.contains(point):
        # {..}....{.^...}
        # {.^...}....{..}
        return point - region2.a + region1.a
    elif region1.contains(point):
        # {^....}....{..}
        # {..}....{^....}
        return point + region2.b - region1.b
    elif region1.b <= point < region2.a:
        # {..}.^..{.....}
        # {.....}.^..{..}
        return point + region1.size() - region2.size()
    else:
        return point

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
    new_cursor_position = project_point_after_swapping(region1, region2, current_cursor_position)

    # make a list of folds to refold
    region_to_refold_list = []
    for folded_region in view.folded_regions():
        if strictly_within(folded_region, region1) or strictly_within(folded_region, region2):
            region_to_refold_list.append(
                sublime.Region(
                    project_point_after_swapping(region1, region2, folded_region.a),
                    project_point_after_swapping(region1, region2, folded_region.b)))

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

    view.fold(region_to_refold_list)


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
    if get_header_level(view.substr(swap_headline_region)) < current_headline_level:
        return

    current_section_region = current_section_info.section_region
    swap_section_region = orgmode_structure.get_section_info(point=swap_headline_region.a).section_region

    swap_regions(view, edit, current_section_region, swap_section_region)
    view.show(view.sel()[0].a)


class ZorgCycleAll(sublime_plugin.TextCommand):
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

        # TODO: кажется можно просто сказать view.unfold(folded_regions)
        # но сначала нужно написать тесты
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


class ZorgMoveNodeUp(sublime_plugin.TextCommand):
    def run(self, edit):
        move_current_node(self.view, edit, up=True)


class ZorgMoveNodeDown(sublime_plugin.TextCommand):
    def run(self, edit):
        move_current_node(self.view, edit, up=False)


class ZorgToggleCheckbox(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        orgmode_structure = OrgmodeStructure(view)
        line_region = orgmode_structure.get_line_region()
        if not line_region:
            return
        line_text = view.substr(line_region)

        match = re.match('^(?:\s+[*]|\s*[-+]|\s*[0-9]*[.]|\s[a-zA-Z][.])\s+\[(.)\].*$', line_text)
        if not match:
            return

        tick_region = sublime.Region(
            line_region.a + match.start(1),
            line_region.a + match.end(1))

        tick_mark = view.substr(tick_region)
        next_tick = {' ': 'X', 'X': ' '}.get(tick_mark, ' ')
        view.replace(edit, tick_region, next_tick)

class ZorgMoveToArchive(sublime_plugin.TextCommand):
    def run(self, edit, silent=True):
        view = self.view
        current_filename = view.file_name()
        document = zorg_parse_document(view)
        archive_template = document.archive
        if archive_template is None:
            archive_template = '%s_archive'

        if '%s' in archive_template:
            if current_filename is None:
                sublime.status_message("File doesn't have a name don't know where to put archive")
                return
            archive_filename = archive_template.replace('%s', current_filename)
        else:
            archive_filename = archive_template

        # TODO: use parsed structure

        # Найти текущую секцию
        orgmode_structure = OrgmodeStructure(view)
        section_info = orgmode_structure.get_section_info()

        # Привести её к уровню 1
        section_text = view.substr(section_info.section_region)
        if section_info.headline_level == 1:
            level1_section_text = section_text
        else:
            level1_section_text = re.sub(
                '^[*]{{{}}}'.format(section_info.headline_level - 1),
                '',
                section_text)
        level1_section_text = '\n' + level1_section_text.strip('\n') + '\n'

        # Записать в архивный файл
        try:
            with open(archive_filename, 'a') as outf:
                outf.write(level1_section_text)
        except IOError as e:
            # Если не ок, жалуемся
            if not silent:
                sublime.error_message("can not use `{}' as archive file: {}".format(archive_filename, e))
            return
        # Если ok, удаляем секцию
        view.erase(edit, section_info.section_region)
        sublime.status_message("Entry is archived to `{}'".format(archive_filename))
        return

class ZorgFollowLink(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        # нужно найти ссылку, внутри которой мы находимся
        orgmode_structure = OrgmodeStructure(view)
        line_region = orgmode_structure.get_line_region()
        line = view.substr(line_region)
        link_list = find_links_in_string(line)
        cursor_point = orgmode_structure.get_cursor_point()
        cursor_in_line = cursor_point - line_region.a

        for link_info in link_list:
            if link_info.start < cursor_in_line < link_info.end:
                current_link = link_info
                break
        else:
            sublime.status_message("cursor is not on the link")
            return

        ref_handlers = {
            'http': self.open_in_browser,
            'https': self.open_in_browser,
            'file': self.open_file,
            'file+sys': self.open_sys_file,
        }
        try:
            url = self.expand_url(orgmode_structure, current_link.reference)
        except RuntimeError as e:
            sublime.status_message(str(e))
            return
        schema = url.split(":", 1)[0]
        if schema in ref_handlers:
            ref_handlers[schema](view, url)
        else:
            self.follow_header_link(view, url)

    def open_in_browser(self, view, url):
        webbrowser.open_new(url)

    def expand_url(self, orgmode_structure, url):
        original_url = url

        expansion_rules = {}
        for special_line in orgmode_structure.iter_special_lines("LINK"):
            fields = special_line.split(None, 1)
            if len(fields) != 2:
                sublime.status_message("Bad link line: {}".format(special_line))
                continue
            abbreviation, replacement = fields
            if abbreviation in expansion_rules:
                sublime.status_message("Link abbreviation `{}' is used multiple times".format(abbreviation))
            expansion_rules[abbreviation] = replacement

        for i in range(30):
            fields = url.split(":", 1)
            if len(fields) != 2:
                return url
            schema, rest = fields
            if schema in expansion_rules:
                url = expansion_rules[schema] % rest
            else:
                return url
        else:
            raise RuntimeError("Expansion limit exceeded, while expanding url: {}".format(original_url))

    def open_file(self, view, url):
        file_path = url.split(':', 1)[-1] # strip scheme
        file_path = os.path.expanduser(file_path)
        window = view.window()
        window.open_file(file_path)

    def open_sys_file(self, view, url):
        file_path = url.split(':', 1)[-1] # strip scheme
        file_path = os.path.expanduser(file_path)
        # TODO: нужно сделать для других типов файлов
        subprocess.check_call(['xdg-open', file_path])

    def follow_header_link(self, view, caption):
        org_document = zorg_parse.parse_org_string(view.substr(sublime.Region(0, view.size())))
        offset = None
        for section in org_document.iter_section():
            text = section.headline.title.get_text()
            if text == caption:
                offset = section.headline.begin

        if offset is None:
            sublime.status_message("can't follow link, text is not found: `{}'".format(caption))
            return
        goto(view, offset)
