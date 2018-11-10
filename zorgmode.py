# -*- coding: utf-8 -*-

import collections
import glob
import itertools
import os
import re
import subprocess
import webbrowser

import sublime_plugin
import sublime

from .mock_sublime import (
    View as TextView,
    Region as TextViewRegion
)

from .zorg_view_parse import (
    LIST_ENTRY_BEGIN_RE,

    OrgControlLine,
    OrgHeadline,
    OrgListParser,
    OrgSection,

    find_child_containing_point,
    org_control_line_get_key_value,
    org_headline_get_text,
    is_point_within_region,
    iter_tree_depth_first,
    next_sibling,
    parse_org_document as parse_org_document_new,
    prev_sibling,
)

try:
    import Default.history_list as history_list_plugin
except ImportError:
    history_list_plugin = None

MAX_HEADLINE_LEVEL = 30
ZORG_AGENDA_FILES = "zorg_agenda_files"
ZORGMODE_SUBLIME_SETTINGS = "zorgmode.sublime-settings"

OrgLinkInfo = collections.namedtuple("OrgLinkInfo", "start,end,reference,text")

URL_RE = re.compile("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")


class ZorgmodeFatalError(RuntimeError):
    pass


class ZorgmodeError(RuntimeError):
    pass


if history_list_plugin:
    def save_position_for_jump_history(view):
        jump_history = history_list_plugin.get_jump_history_for_view(view)
        jump_history.push_selection(view)
else:
    def save_position_for_jump_history(_):
        pass


def goto(view: sublime.View, point):
    save_position_for_jump_history(view)
    view.sel().clear()
    view.sel().add(sublime.Region(point))
    view.show(point)


def find_links_in_string(text):
    processed_end = 0
    link_list = []
    while True:
        start_marker = text.find("[[", processed_end)
        if start_marker == -1:
            break
        end_marker = text.find("]]", start_marker)
        if end_marker == -1:
            break
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

    for m in URL_RE.finditer(text):
        start = m.start()
        end = m.end()
        url = m.group(0)
        link_list.append(
            OrgLinkInfo(
                start=start,
                end=end,
                reference=url,
                text=url))

    return link_list


def view_get_cursor_point(view):
    if len(view.sel()) == 0:
        raise ZorgmodeError("Cannot run this command with no cursor")
    if len(view.sel()) > 1:
        raise ZorgmodeError("Cannot run this command with multiple cursors")
    sel, = view.sel()
    if not sel.empty():
        raise ZorgmodeError("Cannot run this command with selection")
    return sel.a


def view_get_full_region(v):
    if isinstance(v, TextView):
        cls = TextViewRegion
    else:
        assert isinstance(v, sublime.View)
        cls = sublime.Region
    return cls(0, v.size())


def find_view_by_id(view_id):
    for window in sublime.windows():
        for view in window.views():
            if view.id() == view_id:
                return view
    return None


class OrgmodeStructure(object):
    SectionInfo = collections.namedtuple(
        'SectionInfo',
        ['headline_region', 'headline_level', 'section_region', 'content_region'])

    def __init__(self, view):
        self.view = view

    def is_cursor_over_list_entry(self):
        view = self.view

        current_line = view.substr(self.get_line_region())
        return LIST_ENTRY_BEGIN_RE.match(current_line)

    def get_cursor_point(self):
        return view_get_cursor_point(self.view)

    def get_line_region(self, point=None):
        view = self.view
        if point is None:
            point = self.get_cursor_point()
        return view.line(point)

    def parse_current_org_list(self):
        view = self.view

        view_size = view.size()

        # 1. Нужно получить список строк исходного файла.
        line_region_list = view.lines(sublime.Region(0, view_size))
        for region in line_region_list:
            # We want our regions to include trailing '\n'
            if region.b != view_size:
                region.b += 1

        current_line_index, _ = view.rowcol(self.get_cursor_point())

        # 2. Нужно идти назад пока не будем уверены, что списка дальше нет.
        before_org_list_start = current_line_index - 1
        empty_line_count = 0
        while before_org_list_start >= 0:
            line = view.substr(line_region_list[before_org_list_start])
            line_is_empty = not line.strip()
            if line_is_empty:
                empty_line_count += 1
                if empty_line_count >= 2:
                    break
            else:
                empty_line_count = 0

            if line.startswith(" ") or LIST_ENTRY_BEGIN_RE.match(line) or line_is_empty:
                before_org_list_start -= 1
                continue
            break

        # 3. Нужно идти вперёд пока не найдём начало списка.
        org_list_start = before_org_list_start + 1
        while org_list_start < len(line_region_list):
            line = view.substr(line_region_list[org_list_start])
            if LIST_ENTRY_BEGIN_RE.match(line):
                break
            org_list_start += 1
        else:
            raise ZorgmodeError("Cursor is not positioned over list entry")

        # 4. Нужно распарсить лист.
        parser = OrgListParser(view)
        line_idx = org_list_start
        while (
                line_idx < len(line_region_list)
                and parser.try_push_line(line_region_list[line_idx])
        ):
            line_idx += 1
        return parser.finish()

    def get_list_entry_info(self, point=None):
        view = self.view
        current_line_region = self.get_line_region(point=point)
        current_line = view.substr(current_line_region)
        match = re.search(r'^(\s+[*]|\s*[-+]|\s*[0-9]*[.]|\s[a-zA-Z][.])\s+', current_line)
        if match is None:
            return

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
    status_list = ['', 'TODO', 'DONE']
    if len(view.sel()) != 1:
        return
    sel, = view.sel()
    if not sel.empty():
        return

    # - получить строку в которой мы находимся
    current_line_region = view.line(sel)
    current_line_index, _ = view.rowcol(current_line_region.a)
    current_line = view.substr(current_line_region)
    match = re.search(r'^\s*(([-+*]|[*]+)\s)(\s*\w+\b\s*|\s*)?', current_line)
    if match is None:
        return

    # - понять какой таг у нас стоит и где
    status_start = match.end(1)
    spaced_status = match.group(3)
    status_end = match.end(3)

    # - понять какой таг у нас следующий
    try:
        status_index = status_list.index(spaced_status.strip())
    except ValueError:
        status_index = 0
        status_end = status_start

    delta = 1 if forward else -1
    next_status = status_list[(status_index + delta) % len(status_list)]

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


def find_all_in_region(view, expr, region):
    invalid_region = sublime.Region(-1, -1)
    result = []
    pos = region.a
    while True:
        match_region = view.find(expr, pos)
        if match_region == invalid_region:
            break
        if not region.contains(match_region):
            break
        if match_region.a <= pos != region.a:
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
        current_line_index, _ = view.rowcol(current_line_region.a)
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
    if not string:
        raise ValueError("string is not a headline")
    i = None
    for i, c in enumerate(string):
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

    if not is_line_start(view, region1.a):
        raise ValueError("First region must begin at line start")
    if not is_line_start(view, region1.b) and region1.b != view.size():
        raise ValueError("First region must end at line start")

    if not is_line_start(view, region2.a):
        raise ValueError("Second region must begin at line start")
    if not is_line_start(view, region2.b) and region2.b != view.size():
        raise ValueError("Second region must end at line start")

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


def move_current_list_entry(view, edit, up=True):
    # TODO: factorize
    if len(view.sel()) != 1 or not view.sel()[0].empty():
        return

    # найти текущий элемент списка
    orgmode_structure = OrgmodeStructure(view)
    org_list_node = orgmode_structure.parse_current_org_list()

    child = find_child_containing_point(org_list_node, orgmode_structure.get_cursor_point())
    if up:
        sibling = prev_sibling(child)
    else:
        sibling = next_sibling(child)

    if sibling is None:
        return

    swap_regions(view, edit, child.region, sibling.region)
    view.show(view.sel()[0].a)


def move_current_section(view, edit, up=True):
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
        structure = OrgmodeStructure(self.view)
        if structure.is_cursor_over_list_entry():
            move_current_list_entry(self.view, edit, up=True)
        else:
            move_current_section(self.view, edit, up=True)


class ZorgMoveNodeDown(sublime_plugin.TextCommand):
    def run(self, edit):
        structure = OrgmodeStructure(self.view)
        if structure.is_cursor_over_list_entry():
            move_current_list_entry(self.view, edit, up=False)
        else:
            move_current_section(self.view, edit, up=False)


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
    def run(self, edit, silent=False):
        try:
            self.run_impl(edit)
        except ZorgmodeError as e:
            sublime.status_message(str(e))
        except ZorgmodeFatalError as e:
            if silent:
                sublime.status_message(str(e))
            else:
                sublime.error_message(str(e))

    def run_impl(self, edit):
        view = self.view
        current_filename = view.file_name()

        org_root = parse_org_document_new(view, sublime.Region(0, view.size()))

        archive_template = None
        cursor = view_get_cursor_point(view)
        headline_under_cursor = None
        for item in iter_tree_depth_first(org_root):
            if isinstance(item, OrgControlLine):
                key, value = org_control_line_get_key_value(item)
                if key == "ARCHIVE":
                    archive_template = value
            elif isinstance(item, OrgHeadline):
                if is_point_within_region(cursor, item.region):
                    assert headline_under_cursor is None
                    headline_under_cursor = item

        if archive_template is None:
            archive_template = '%s_archive'

        if '%s' in archive_template:
            if current_filename is None:
                raise ZorgmodeError("Don't know where to put archive because file doesn't have a name")
            archive_filename = archive_template.replace('%s', current_filename)
        else:
            archive_filename = archive_template

        # Привести её к уровню 1
        # TODO: это упячечный способ приводить секцию к уровню 1 (из-за #+BEGIN_SRC)
        section = headline_under_cursor.parent
        assert isinstance(section, OrgSection)
        section_text = view.substr(section.region)
        if section.level == 1:
            level1_section_text = section_text
        else:
            level1_section_text = re.sub(
                '^[*]{{{}}}'.format(section.level - 1),
                '',
                section_text)
        level1_section_text = '\n' + level1_section_text.strip('\n') + '\n'

        # Записать в архивный файл
        try:
            with open(archive_filename, 'a') as outf:
                outf.write(level1_section_text)
        except IOError as e:
            # Если не ок, жалуемся
            raise ZorgmodeFatalError("can not use `{}' as archive file: {}".format(archive_filename, e))
        # Если ok, удаляем секцию
        view.erase(edit, section.region)
        sublime.status_message("Entry is archived to `{}'".format(archive_filename))


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

    @staticmethod
    def open_in_browser(_, url):
        webbrowser.open_new(url)

    @staticmethod
    def expand_url(orgmode_structure, url):
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

    @staticmethod
    def open_file(view, url):
        file_path = url.split(':', 1)[-1]  # strip scheme
        file_path = os.path.expanduser(file_path)
        window = view.window()
        window.open_file(file_path)

    @staticmethod
    def open_sys_file(_, url):
        file_path = url.split(':', 1)[-1]  # strip scheme
        file_path = os.path.expanduser(file_path)
        # TODO: нужно сделать для других типов файлов
        subprocess.check_call(['xdg-open', file_path])

    @staticmethod
    def follow_header_link(view, caption):
        org_root = parse_org_document_new(view, sublime.Region(0, view.size()))

        offset = None
        for item in iter_tree_depth_first(org_root):
            if not isinstance(item, OrgHeadline):
                continue
            text = org_headline_get_text(item)
            if text == caption:
                offset = item.region.a

        if offset is None:
            sublime.status_message("can't follow link, text is not found: `{}'".format(caption))
            return
        goto(view, offset)


class Agenda(object):
    AgendaLine = collections.namedtuple("AgendaLine", ["text", "meta_info"])
    AgendaItemMetaInfo = collections.namedtuple("AgendaItemMetaInfo", [
        "file_name",
        "view_id",
        "line_index_0",
        "original_text",
    ])

    def __init__(self):
        self._todos = []
        self._warnings = []
        self._final_lines = None

    @staticmethod
    def _check_line(text):
        if "\n" in text:
            raise ValueError("It's not a single line")

    def get_line_meta_info(self, line_index_0: int) -> AgendaItemMetaInfo:
        return self._final_lines[line_index_0].meta_info

    def add_warning(self, msg):
        self._check_line(msg)
        self._warnings.append(self.AgendaLine("#+WARNING: " + msg, None))

    def add_todo_item(self, headline_node):
        view = headline_node.view
        region = headline_node.region
        original_text = headline_node.view.substr(region)
        _, stripped_text = original_text.split(None, 1)
        stripped_text = stripped_text.rstrip("\n")

        row, _ = view.rowcol(region.a)
        meta_info = self.AgendaItemMetaInfo(
            file_name=view.file_name(),
            view_id=view.id(),
            line_index_0=row,
            original_text=original_text,
        )
        self._check_line(stripped_text)
        self._todos.append(self.AgendaLine("  TODO:    " + stripped_text, meta_info))

    def finalize(self):
        self._final_lines = []
        self._final_lines.append(self.AgendaLine("#+BEGIN_AGENDA", None))
        self._final_lines += self._warnings
        self._final_lines += self._todos
        self._final_lines.append(self.AgendaLine("#+END_AGENDA", None))
        iter_lines = (line.text for line in self._final_lines)
        return "\n".join(iter_lines) + "\n"


class AgendaRegistry:
    def __init__(self):
        self._agenda_registry = {}

    def save_agenda(self, view, agenda):
        self._run_gc()
        self._agenda_registry[view.id()] = agenda

    def get_agenda(self, view) -> Agenda:
        return self._agenda_registry.get(view.id(), None)

    def _run_gc(self):
        active_view_ids = set()
        for window in sublime.windows():
            for view in window.views():
                active_view_ids.add(view.id())
        for_gc = []
        for id_ in self._agenda_registry:
            if id_ not in active_view_ids:
                for_gc.append(id_)

        for id_ in for_gc:
            del self._agenda_registry[id_]


AGENDA_REGISTRY = AgendaRegistry()


def get_zorgmode_syntax():
    lst = sublime.find_resources("zorgmode.sublime-syntax")
    if not lst:
        return None
    return lst[0]


class QuickPanelAgenda(object):
    def __init__(self, window):
        view = window.find_output_panel("output.agenda")
        if view is not None:
            window.destroy_output_panel("output.agenda")
        view = window.create_output_panel("agenda")

        self.view = view
        self._window = window

    def focus(self):
        self._window.run_command("show_panel", {"panel": "output.agenda"})
        self._window.focus_view(self.view)


class NewTabAgenda(object):
    def __init__(self, window):
        self.view = window.new_file()
        self.view.set_scratch(True)
        self._window = window

    def focus(self):
        self._window.focus_view(self.view)


def expand_file_list(file_list, agenda_output):
    result = []
    unique = set()
    for file_name in file_list:
        file_name = os.path.expanduser(file_name)
        if not os.path.isabs(file_name):
            agenda_output.add_warning(
                "Path `{file_name} in `{settings}' is not absolute."
                .format(
                    file_name=file_name,
                    settings=ZORG_AGENDA_FILES
                )
            )
            continue

        match_found = False
        for match_file_name in glob.iglob(file_name):
            if match_file_name not in unique:
                result.append(match_file_name)
                unique.add(match_file_name)
            match_found = True

        if not match_found:
            agenda_output.add_warning(
                "Cannot find `{file_name}' from `{setting}'"
                .format(file_name=file_name, setting=ZORG_AGENDA_FILES)
            )
    return result


class ZorgTodoList(sublime_plugin.TextCommand):
    def run(self, edit, show_in="quick_panel", zorg_agenda_files=None):
        view = self.view

        zorg_syntax = get_zorgmode_syntax()
        if zorg_syntax is None:
            sublime.status_message("Cannot find zorgmode syntax file. Probably zorgmode is not installed correctly")
            return

        output_cls = {
            "quick_panel": QuickPanelAgenda,
            "new_tab": NewTabAgenda,
        }[show_in]

        window = view.window()

        agenda_output = Agenda()

        if zorg_agenda_files is None:
            settings = sublime.load_settings("zorgmode.sublime-settings")
            zorg_agenda_files = settings.get(ZORG_AGENDA_FILES, [])
            zorg_agenda_files = expand_file_list(zorg_agenda_files, agenda_output)

        if not zorg_agenda_files:
            # TODO: documentation reference
            agenda_output.add_warning(
                "Cannot find nonempty `{option_name}' in settings."
                .format(option_name=ZORG_AGENDA_FILES)
            )

        def get_view_for_system_file(file_name):
            try:
                v = window.find_open_file(file_name)
                if v is not None:
                    return v
                with open(file_name) as inf:
                    t = inf.read()
                return TextView(t, file_name)
            except Exception as e:
                agenda_output.add_warning(
                    "Error occurred while reading file `{file_name}': {error}"
                    .format(
                        file_name=file_name,
                        error=str(e)
                    )
                )
                return None

        def get_view_for_special_file(file_name):
            m = re.match("/dev/sublimetext_view/(\d+)$", file_name)
            if not m:
                agenda_output.add_warning("Bad file: {}".format(file_name))
                return None
            view_id = int(m.group(1))
            v = find_view_by_id(view_id)
            if v is None:
                agenda_output.add_warning("Cannot find the view with index {} for file {}".format(view_id, file_name))
                return None
            return v

        for file_name in zorg_agenda_files:
            if file_name.startswith("/dev/sublimetext_view/"):
                # Special case useful for tests when we get text from already opened view
                file_view = get_view_for_special_file(file_name)
            else:
                file_view = get_view_for_system_file(file_name)
            if file_view is None:
                continue

            org_root = parse_org_document_new(file_view, view_get_full_region(file_view))
            for headline in iter_tree_depth_first(org_root):
                if not isinstance(headline, OrgHeadline):
                    continue
                text = headline.text().rstrip('\n')
                m = re.match("^[*]+\s(TODO\s.*)$", text)
                if m:
                    agenda_output.add_todo_item(headline)

        output = output_cls(window)

        output.view.set_syntax_file(zorg_syntax)
        output.view.run_command("append", {"characters": agenda_output.finalize(), "force": True})
        output.view.set_read_only(True)

        AGENDA_REGISTRY.save_agenda(output.view, agenda_output)

        output.focus()


def agenda_meta_info_get_or_create_view(window: sublime.Window, meta_info: Agenda.AgendaItemMetaInfo):
    if meta_info.file_name is not None:
        view = window.find_open_file(meta_info.file_name)
        if view is not None:
            return view
        return window.open_file(meta_info.file_name)

    for view in window.views():
        if view.id() == meta_info.view_id:
            return view

    raise ZorgmodeError("Cannot find file for this item")


class ZorgAgendaGoto(sublime_plugin.TextCommand):
    def run(self, edit):
        try:
            agenda_view = self.view
            window = agenda_view.window()
            agenda = AGENDA_REGISTRY.get_agenda(agenda_view)

            # 1. Получить номер текущей строки.
            agenda_line_index_0, _ = agenda_view.rowcol(view_get_cursor_point(agenda_view))

            # 2. Получить meta_info
            meta_info = agenda.get_line_meta_info(agenda_line_index_0)

            # 3. По meta_info надо найти подходящий view и активировать его.
            file_view = agenda_meta_info_get_or_create_view(window, meta_info)

            match_list = file_view.find_all(meta_info.original_text, sublime.LITERAL)

            # 4. Найти нужную позицию во view,
            best_region = None
            best_distance = None

            for m in match_list:
                cur_line_index_0, _ = file_view.rowcol(m.a)
                cur_distance = abs(cur_line_index_0 - meta_info.line_index_0)
                if (
                        best_region is None
                        or best_distance > cur_distance
                ):
                    best_region = m
                    best_distance = cur_distance

            if best_region is None:
                raise ZorgmodeError("Cannot find this item anymore")

            # Перейти на начало соответствующей строки
            group_idx, _ = window.get_view_index(file_view)
            window.focus_view(file_view)
            window.focus_group(group_idx)

            goto(file_view, best_region.a)

        except ZorgmodeError as e:
            sublime.status_message(str(e))


def is_agenda_list_command_visible(view):
    return (
        view.file_name() is not None
        and view.settings().get("syntax").endswith("zorgmode.sublime-syntax")
    )


class ZorgAgendaListAddFile(sublime_plugin.TextCommand):
    def is_visible(self):
        return is_agenda_list_command_visible(self.view)

    def run(self, edit, dest="front"):
        try:
            view = self.view
            file_name = view.file_name()
            if file_name is None:
                raise ZorgmodeFatalError("Cannot add file without name to zorg_agenda_list")
            file_name = os.path.abspath(file_name)
            settings = sublime.load_settings("zorgmode.sublime-settings")
            zorg_agenda_files = settings.get(ZORG_AGENDA_FILES, [])

            new_zorg_agenda_files = []
            if dest == "front":
                new_zorg_agenda_files.append(file_name)
            for f in zorg_agenda_files:
                if f != file_name:
                    new_zorg_agenda_files.append(f)
            if dest == "end":
                new_zorg_agenda_files.append(file_name)
            settings.set(ZORG_AGENDA_FILES, new_zorg_agenda_files)
            sublime.save_settings("zorgmode.sublime-settings")
        except ZorgmodeError as e:
            sublime.status_message(str(e))
        except ZorgmodeFatalError as e:
            sublime.error_message(str(e))


class ZorgAgendaListRemoveFile(sublime_plugin.TextCommand):
    def is_visible(self):
        return is_agenda_list_command_visible(self.view)

    def is_enabled(self):
        settings = sublime.load_settings("zorgmode.sublime-settings")
        zorg_agenda_files = settings.get(ZORG_AGENDA_FILES, [])
        return self.view.file_name() is not None and os.path.abspath(self.view.file_name()) in zorg_agenda_files

    def run(self, edit):
        try:
            view = self.view
            file_name = view.file_name()
            if file_name is None:
                raise ZorgmodeFatalError("Cannot add file without name to zorg_agenda_list")
            file_name = os.path.abspath(file_name)
            settings = sublime.load_settings("zorgmode.sublime-settings")
            zorg_agenda_files = settings.get(ZORG_AGENDA_FILES, [])

            new_zorg_agenda_files = []
            for f in zorg_agenda_files:
                if f != file_name:
                    new_zorg_agenda_files.append(f)
            settings.set(ZORG_AGENDA_FILES, new_zorg_agenda_files)
            sublime.save_settings("zorgmode.sublime-settings")
        except ZorgmodeError as e:
            sublime.status_message(str(e))
        except ZorgmodeFatalError as e:
            sublime.error_message(str(e))
