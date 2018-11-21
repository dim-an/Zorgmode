#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import contextlib
import re
import sys

# NOTE: this module doesn't import sublime module so we can mock view/region etc in tests

LIST_ENTRY_BEGIN_RE = re.compile(r"^(\s+[*]|\s*[-+]|\s*[0-9]+[.]|\s[a-zA-Z][.])\s+")
HEADLINE_RE = re.compile(
    '^([*]+) \s+'  # STARS group 1
    '(?: ([A-Za-z0-9]+)\s+ )?'  # KEYWORD group 2
    '(?: \[[#]([a-zA-Z])\]\s+)?'  # PRIORITY group 3
    '(.*?)'  # TITLE -- match in nongreedy fashion group 4
    '\s* (:(?: [a-zA-Z0-9_@#]+ :)+)? \s*$',  # TAGS group 5
    re.VERBOSE
)
CONTROL_LINE_RE = re.compile(
    "^\#\+"  # prefix
    "([A-Z_]+) :"  # key
    "\s* (.*)",  # value
    re.VERBOSE
)
BEGIN_SRC_RE = re.compile(
    r"^\#\+BEGIN_SRC\b.*$"
)
END_SRC_RE = re.compile(
    r"^\#\+END_SRC\b.*$"
)

BEGIN_EXAMPLE_RE = re.compile(
    r"^\#\+BEGIN_EXAMPLE\b.*$"
)
END_EXAMPLE_RE = re.compile(
    r"^\#\+END_EXAMPLE\b.*$"
)
COLON_LINE_EXAMPLE_RE = re.compile(
    r"^\s*:.*$"
)
KEYWORD_SET = frozenset(["TODO", "DONE"])


def is_point_within_region(point, region):
    return region.a <= point < region.b


def line_is_list_entry_begin(line_text):
    return LIST_ENTRY_BEGIN_RE.match(line_text)


def line_is_headline(line_text):
    return HEADLINE_RE.match(line_text)


def iter_tree_depth_first(node):
    for child in node.children:
        for n in iter_tree_depth_first(child):
            yield n
    yield node


def find_child_containing_point(node, point):
    if not is_point_within_region(point, node.region):
        return None

    while node.children:
        for child in node.children:
            if is_point_within_region(point, child.region):
                node = child
                break
        else:
            return node
    return node


def sibling(node, offset, sibling_type_filter=None):
    if node.parent is None:
        return None
    siblings = node.parent.children
    if sibling_type_filter:
        siblings = [s for s in siblings if isinstance(s, sibling_type_filter)]
    idx = siblings.index(node)
    if idx == -1:
        raise AssertionError("Cannot find node in the list of its parent children")
    if 0 <= idx + offset < len(siblings):
        return siblings[idx + offset]
    return None


def next_sibling(node, sibling_type_filter=None):
    return sibling(node, 1, sibling_type_filter)

    
def prev_sibling(node, sibling_type_filter=None):
    return sibling(node, -1, sibling_type_filter)


def view_full_lines(view, region):
    # NOTE: line ending might be either '\r\n' or '\n'
    # TODO: test this function
    line_region_list = view.lines(region)
    for i in range(len(line_region_list) - 1):
        line_region_list[i].b = line_region_list[i+1].a
    if line_region_list:
        line_region_list[-1].b = view.size()
    return line_region_list


def parse_org_document_new(view, region):
    builder = OrgTreeBuilder(view)
    parser_input = ParserInput(view, region)

    parse_global_scope(parser_input, builder)

    return builder.finish()


class OrgViewNode(object):
    def __init__(self, view, parent):
        self.children = []
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        self.region = None
        self.view = view

    def text(self):
        return self.view.substr(self.region)

    def __repr__(self):
        text = _node_text(self)
        if len(text) > 55:
            text = "{} ... {}".format(text[:25], text[-25:])
        attrs = self._debug_attrs()
        if attrs != "":
            attrs += ", "
        return "{cls}({attrs}{str_repr})".format(cls=type(self).__name__, attrs=attrs, str_repr=repr(text))

    def _debug_attrs(self):
        return ""

    def debug_print(self, indent=None, file=None):
        if file is None:
            file = sys.stdout
        if indent is None:
            indent = 0
        indent_str = " " * indent
        file.write(indent_str + repr(self) + "\n")
        for c in self.children:
            c.debug_print(indent+2)
        if indent == 0:
            file.flush()


class OrgRoot(OrgViewNode):
    node_type = "root"

    def __init__(self, view):
        super(OrgRoot, self).__init__(view, None)


class OrgSection(OrgViewNode):
    node_type = "section"

    def __init__(self, view, parent, level):
        super(OrgSection, self).__init__(view, parent)
        self.level = level

    def _debug_attrs(self):
        return "level={}".format(self.level)


class OrgHeadline(OrgViewNode):
    node_type = "headline"

    def __init__(self, view, parent, level):
        super(OrgHeadline, self).__init__(view, parent)
        self.level = level

    def _debug_attrs(self):
        return "level={}".format(self.level)

class OrgSrcBlock(OrgViewNode):
    node_type = "src_block"


def org_headline_get_text(headline: OrgHeadline):
    line = headline.view.substr(headline.region)
    m = HEADLINE_RE.match(line)
    assert m is not None

    keyword = m.group(2)

    title_begin = m.start(4)
    title_end = m.end(4)
    if keyword is not None and keyword not in KEYWORD_SET:
        title_begin = m.start(2)
    return line[title_begin:title_end]


def org_headline_get_tag_list(headline: OrgHeadline):
    line = headline.view.substr(headline.region)
    m = HEADLINE_RE.match(line)
    assert m is not None

    tag_group = m.group(5)
    if tag_group is not None:
        return tag_group.strip(':').split(':')
    return []


class OrgList(OrgViewNode):
    node_type = "list"

    def __init__(self, view, parent, indent):
        super(OrgList, self).__init__(view, parent)
        self.indent = indent


class OrgListEntry(OrgViewNode):
    node_type = "list_entry"

    def __init__(self, view, parent, indent):
        super(OrgListEntry, self).__init__(view, parent)
        self.indent = indent


class OrgControlLine(OrgViewNode):
    node_type = "control_line"

    def __init__(self, view, parent):
        super(OrgControlLine, self).__init__(view, parent)


def org_control_line_get_key_value(control_line: OrgControlLine):
    line = control_line.view.substr(control_line.region)
    m = CONTROL_LINE_RE.match(line)
    assert m is not None
    return m.group(1), m.group(2)


class OrgTreeBuilder:
    def __init__(self, view):
        self._root = OrgRoot(view)
        section = OrgSection(view, self._root, 0)
        self._stack = [self._root, section]
        self._context_stack = [2]

    def top(self):
        return self._stack[-1]

    def pop(self):
        self._stack.pop()

    def push(self, node):
        self._stack.append(node)

    def finish(self):
        self._stack = None
        return self._root

    @contextlib.contextmanager
    def push_context(self):
        curlen = len(self._stack)
        self._context_stack.append(curlen)
        yield
        self._context_stack.pop()
        if len(self._stack) > curlen:
            del self._stack[curlen:]

    def is_context_empty(self):
        return len(self._stack) <= self._context_stack[-1]


class ParserInput:
    def __init__(self, view, region):
        self._full_line_region_list = view_full_lines(view, region)
        self._idx = 0
        self.view = view

    def get_current_line_region(self):
        if self._idx < len(self._full_line_region_list):
            return self._full_line_region_list[self._idx]
        else:
            return None

    def next_line(self):
        self._idx += 1


def parse_global_scope(parser_input: ParserInput, builder: OrgTreeBuilder):
    view = parser_input.view
    while parser_input.get_current_line_region() is not None:
        region = parser_input.get_current_line_region()
        line = view.substr(region)
        line = line.rstrip('\n')
        m = HEADLINE_RE.match(line)
        if m is not None:
            headline_level = len(m.group(1))
            assert headline_level > 0
            while (
                    not isinstance(builder.top(), OrgSection)
                    or builder.top().level >= headline_level
            ):
                builder.pop()

            new_section = OrgSection(view, builder.top(), headline_level)
            headline = OrgHeadline(view, new_section, headline_level)
            builder.push(new_section)
            _extend_region(headline, region)
            parser_input.next_line()
            continue

        m = LIST_ENTRY_BEGIN_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_list(parser_input, builder)
            continue

        m = BEGIN_SRC_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_example_block(parser_input, builder, BEGIN_EXAMPLE_RE, END_EXAMPLE_RE)
            continue

        m = BEGIN_EXAMPLE_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_example_block(parser_input, builder, BEGIN_EXAMPLE_RE, END_EXAMPLE_RE)
            continue

        m = COLON_LINE_EXAMPLE_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_example_block(parser_input, builder, COLON_LINE_EXAMPLE_RE)

        m = CONTROL_LINE_RE.match(line)
        if m is not None:
            control_line = OrgControlLine(view, builder.top())
            _extend_region(control_line, region)
            parser_input.next_line()
            continue

        _extend_region(builder.top(), region)
        parser_input.next_line()
        continue


def parse_list(parser_input: ParserInput, builder: OrgTreeBuilder):
    view = parser_input.view
    empty_lines = 0
    while parser_input.get_current_line_region() is not None:
        region = parser_input.get_current_line_region()
        line = view.substr(region)

        if line.startswith("*"):
            break

        line_is_empty = not bool(line.strip())
        if line_is_empty:
            empty_lines += 1
            if empty_lines >= 2:
                return
            parser_input.next_line()
            continue
        else:
            empty_lines = 0

        indent = _calc_indent(line)
        m = LIST_ENTRY_BEGIN_RE.match(line)
        if m is not None:
            while (
                isinstance(builder.top(), OrgList) and builder.top().indent > indent
                or isinstance(builder.top(), OrgListEntry) and builder.top().indent >= indent
            ):
                builder.pop()

            if (
                not isinstance(builder.top(), OrgList)
                or builder.top().indent < indent
            ):
                builder.push(OrgList(view, builder.top(), indent))

            builder.push(OrgListEntry(view, builder.top(), indent))
            _extend_region(builder.top(), region)
            parser_input.next_line()
            continue

        while (
            not builder.is_context_empty()
            and not (
                isinstance(builder.top(), OrgListEntry)
                and builder.top().indent < indent
            )
        ):
            builder.pop()

        if builder.is_context_empty():
            return

        assert isinstance(builder.top(), OrgListEntry)
        _extend_region(builder.top(), region)
        parser_input.next_line()


def parse_example_block(parser_input: ParserInput, builder: OrgTreeBuilder, begin_re, end_re):
    view = parser_input.view
    region = parser_input.get_current_line_region()
    if region is None:
        return
    line = view.substr(region)
    m = begin_re.match(line)
    if m is None:
        return
    src_block = OrgSrcBlock(view, builder.top())
    builder.push(src_block)
    _extend_region(src_block, region)
    parser_input.next_line()

    while True:
        region = parser_input.get_current_line_region()
        if region is None:
            return
        line = view.substr(region)
        _extend_region(src_block, region)
        parser_input.next_line()
        if end_re is None:
            m = begin_re.match(line)
            if m is None:
                break
        else:
            m = end_re.match(line)
            if m is not None:
                break
    builder.pop()

#
# Details
#

def _calc_indent(line):
    indent = 0
    for c in line:
        if c == ' ':
            indent += 1
        else:
            break
    return indent


def _extend_region(node, region):
    # we don't want to be dependent on region class so we'll derive region class from runtime
    region_cls = type(region)
    while node:
        if node.region is None:
            node.region = region
        else:
            new_region = region_cls(node.region.a, region.b)
            node.region = new_region
        node = node.parent


def _node_text(node):
    return node.view.substr(node.region)


if __name__ == '__main__':
    import unittest

    import mock_sublime

    class TestListParsing(unittest.TestCase):
        def test_simple_list(self):
            view = mock_sublime.View(
                " - some list item\n"
                " - another list item\n"
            )

            parser = OrgListParser(view)
            for region in view.sp_iter_all_line_regions():
                result = parser.try_push_line(region)
                self.assertTrue(result)
            result = parser.finish()
            self.assertEqual(len(result.children), 1)
            self.assertEqual(len(result.children[0].children), 2)
            self.assertEqual(_node_text(result.children[0].children[0]), " - some list item")
            self.assertEqual(_node_text(result.children[0].children[1]), " - another list item")

        def test_simple_list_with_child(self):
            view = mock_sublime.View(
                " - parent 1\n"
                "   - child\n"
                " - parent 2\n"
            )

            result = parse_org_document_new(view, mock_sublime.Region(0, view.size()))
            self.assertEqual(len(result.children), 1)
            self.assertEqual(len(result.children[0].children), 2)
            self.assertEqual(_node_text(result.children[0].children[0]), " - parent 1\n   - child")
            self.assertEqual(len(result.children[0].children[0].children), 1)
            self.assertEqual(_node_text(result.children[0].children[0].children[0]), "   - child")
            self.assertEqual(_node_text(result.children[0].children[1]), " - parent 2")

        def test_list_with_text(self):
            view = mock_sublime.View(
                " - parent 1\n"
                "  1111\n"
                "  * child 1\n"
                "  2222\n"
                "  * child 2\n"
                "  3333\n"
                "  * child 3\n"
                "  4444\n"
                " - parent 2\n"
                "  5555\n"
            )

            parser = OrgListParser(view)
            for region in view.sp_iter_all_line_regions():
                result = parser.try_push_line(region)
                self.assertTrue(result)
            result = parser.finish()
            self.assertEqual(len(result.children), 1)
            self.assertEqual(len(result.children[0].children), 2)
            parent1, parent2 = result.children[0].children
            self.assertEqual(
                _node_text(parent1),
                " - parent 1\n"
                "  1111\n"
                "  * child 1\n"
                "  2222\n"
                "  * child 2\n"
                "  3333\n"
                "  * child 3\n"
                "  4444"
            )
            self.assertEqual(len(parent1.children), 3)

            for num, child_lst in enumerate(parent1.children, 1):
                self.assertEqual(len(child_lst.children), 1)
                child_entry, = child_lst.children
                self.assertEqual(_node_text(child_entry), "  * child {}".format(num))

    class GlobalScopeParsing(unittest.TestCase):
        def test_headline_parsing(self):
            view = mock_sublime.View(
                "* This is org headline\n"
                "** TODO headline 2\n"
                "*** DONE headline 3\n"
                "**** TODO [#b] headline 4\n"
                "** UNDONE HEADLINE 5\n"
                "** UNDONE [#a] HeAdLiNe 6\n"
                "*** more headlines 7 :tag1:tag2:\n"
            )

            root = parse_org_document_new(view, mock_sublime.Region(0, view.size()))

            headline_item_list = []
            for item in iter_tree_depth_first(root):
                if isinstance(item, OrgHeadline):
                    headline_item_list.append((
                        org_headline_get_text(item),
                        item.level,
                        org_headline_get_tag_list(item)
                    ))

            self.assertEqual(headline_item_list, [
                ("This is org headline", 1, []),
                ("headline 2", 2, []),
                ("headline 3", 3, []),
                ("headline 4", 4, []),
                ("UNDONE HEADLINE 5", 2, []),
                ("UNDONE [#a] HeAdLiNe 6", 2, []),
                ("more headlines 7", 3, ["tag1", "tag2"]),
            ])

        def test_control_line_parsing(self):
            view = mock_sublime.View(
                "#+ARCHIVE: foo\n"
                "#+BAR: QUX\n"
                "#+GG: once upon a time...\n"
                "#+BEGIN_SRC\n"
                "#+END_SRC\n"
            )
            root = parse_org_document_new(view, mock_sublime.Region(0, view.size()))

            all_control_key_value_list = []
            for item in iter_tree_depth_first(root):
                if isinstance(item, OrgControlLine):
                    all_control_key_value_list.append(org_control_line_get_key_value(item))

            self.assertEqual(all_control_key_value_list, [
                ("ARCHIVE", "foo"),
                ("BAR", "QUX"),
                ("GG", "once upon a time..."),
            ])

    unittest.main()
