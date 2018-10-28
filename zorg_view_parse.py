#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

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
    "(.*)",  # value
    re.VERBOSE
)


def is_point_within_region(point, region):
    return region.a <= point < region.b


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


def sibling(node, offset):
    if node.parent is None:
        return None
    siblings = node.parent.children
    idx = siblings.index(node)
    if idx == -1:
        raise AssertionError("Cannot find node in the list of its parent children")
    if not (0 <= idx + offset < len(siblings)):
        return None
    return siblings[idx + offset]


def next_sibling(node):
    return sibling(node, 1)

    
def prev_sibling(node):
    return sibling(node, -1)


def view_full_lines(view, region):
    # NOTE: line ending might be either '\r\n' or '\n'
    # TODO: test this function
    line_region_list = view.lines(region)
    for i in range(len(line_region_list) - 1):
        line_region_list[i].b = line_region_list[i+1].a
    if line_region_list:
        line_region_list[-1].b = view.size()
    return line_region_list


def parse_org_document(view, region):
    # 1. Получить список линий начиная с позиции
    full_line_region_list = view_full_lines(view, region)

    # 2. скармливать их пока не нажрёмся.
    parser = OrgGlobalScopeParser(view)
    for line_region in full_line_region_list:
        if not parser.try_push_line(line_region):
            break

    return parser.finish()


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
        return "{cls}({str_repr})".format(cls=type(self).__name__, str_repr=repr(_node_text(self)))

    def debug_print(self, indent=None, file=None):
        if indent is None:
            indent = 0
        indent_str = " " * indent
        print(indent_str + repr(self), file=file)
        for c in self.children:
            c.debug_print(indent+2)


class OrgRoot(OrgViewNode):
    node_type = "root"

    def __init__(self, view):
        super(OrgRoot, self).__init__(view, None)


class OrgSection(OrgViewNode):
    node_type = "section"

    def __init__(self, view, parent, level):
        super(OrgSection, self).__init__(view, parent)
        self.level = level


class OrgHeadline(OrgViewNode):
    node_type = "headline"

    def __init__(self, view, parent, level):
        super(OrgHeadline, self).__init__(view, parent)
        self.level = level


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
        super(OrgControlLine, self).__init(view, parent)


class OrgGlobalScopeParser(object):
    def __init__(self, view):
        root = OrgRoot(view)
        section = OrgSection(view, root, 0)
        self._root = root
        self._stack = [root, section]
        self._view = view

    def try_push_line(self, region):
        line = self._view.substr(region)
        m = HEADLINE_RE.match(line)
        if m is not None:
            headline_level = len(m.group(1))
            assert headline_level > 0
            while (
                not isinstance(self._stack[-1], OrgSection)
                or self._stack[-1].level >= headline_level
            ):
                self._stack.pop()

            new_section = OrgSection(self._view, self._stack[-1], headline_level)
            headline = OrgHeadline(self._view, new_section, headline_level)
            self._stack.append(new_section)
            _extend_region(headline, region)
            return True

        m = CONTROL_LINE_RE.match(line)
        if m is not None:
            control_line = OrgControlLine(self._view, self._root)
            _extend_region(control_line, region)
            return True

        _extend_region(self._stack[-1], region)
        return True

    def finish(self):
        self._stack = None
        return self._root


class OrgListParser(object):
    def __init__(self, view):
        self._result = OrgRoot(view)
        self._stack = [self._result]
        self._view = view
        self._empty_lines = 0

    def try_push_line(self, region):
        line = self._view.substr(region)

        if line.startswith("*"):
            return False

        line_is_empty = not bool(line.strip())
        if line_is_empty:
            self._empty_lines += 1
            return bool(self._empty_lines < 2)
        else:
            self._empty_lines = 0

        indent = _calc_indent(line)
        m = LIST_ENTRY_BEGIN_RE.match(line)
        if m is not None:
            while (
                self._stack[-1].node_type != "root"
                and (
                    isinstance(self._stack[-1], OrgList) and self._stack[-1].indent > indent
                    or isinstance(self._stack[-1], OrgListEntry) and self._stack[-1].indent >= indent
                )
            ):
                self._stack.pop()
                assert self._stack

            if (
                not isinstance(self._stack[-1], OrgList)
                or self._stack[-1].indent < indent
            ):
                self._stack.append(OrgList(self._view, self._stack[-1], indent))

            self._stack.append(OrgListEntry(self._view, self._stack[-1], indent))
            _extend_region(self._stack[-1], region)
            return True

        while (
            self._stack
            and not (
                isinstance(self._stack[-1], OrgListEntry)
                and self._stack[-1].indent < indent)
        ):
            self._stack.pop()

        if not self._stack:
            return False

        assert isinstance(self._stack[-1], OrgListEntry)
        _extend_region(self._stack[-1], region)
        return True
    
    def finish(self):
        self._stack = None
        return self._result


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

            parser = OrgListParser(view)
            for region in view.sp_iter_all_line_regions():
                result = parser.try_push_line(region)
                self.assertTrue(result)
            result = parser.finish()
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

    unittest.main()
