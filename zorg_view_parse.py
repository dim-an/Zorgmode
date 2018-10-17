#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

# NOTE: this module doesn't import sublime module so we can mock view/region etc in tests

LIST_ENTRY_BEGIN_RE = re.compile(r"^(\s+[*]|\s*[-+]|\s*[0-9]*[.]|\s[a-zA-Z][.])\s+")


class OrgViewNode(object):
    def __init__(self, view, parent):
        self.children = []
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        self.region = None
        self.view = view

    def __repr__(self):
        return "{cls}({str_repr})".format(cls=type(self).__name__, str_repr=repr(node_text(self)))

    def debug_print(self, indent=None):
        if indent is None:
            indent = 0
        indent_str = " " * indent
        print(indent_str + repr(self))
        for c in self.children:
            c.debug_print(indent+2)
    

class OrgRoot(OrgViewNode):
    node_type = "root"
    def __init__(self, view):
        super(OrgRoot, self).__init__(view, None)


class OrgSection(OrgViewNode):
    node_type = "section"


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


def extend_region(node, region):
    # we don't want to be dependent on region class so we'll derive region class from runtime
    region_cls = type(region)
    while node:
        if node.region is None:
            node.region = region
        else:
            new_region = region_cls(node.region.a, region.b)
            node.region = new_region
        node = node.parent


class OrgListParser(object):
    def __init__(self, view):
        self.stack = [OrgRoot(view)]
        self.view = view

    def try_push_line(self, region):
        line = self.view.substr(region)
        m = LIST_ENTRY_BEGIN_RE.match(line)
        if m is not None:
            indent = 0
            for c in line:
                if c != ' ':
                    break
                indent += 1
            while (
                self.stack[-1].node_type != "root"
                and (
                    isinstance(self.stack[-1], OrgList) and self.stack[-1].indent > indent
                    or isinstance(self.stack[-1], OrgListEntry) and self.stack[-1].indent >= indent
                )
            ):
                self.stack.pop()
                assert self.stack

            if (
                not isinstance(self.stack[-1], OrgList)
                or self.stack[-1].indent < indent
            ):
                self.stack.append(OrgList(self.view, self.stack[-1], indent))

            self.stack.append(OrgListEntry(self.view, self.stack[-1], indent))
            extend_region(self.stack[-1], region)
            return True
    
    def finish(self):
        result = self.stack[0]
        self.stack = None
        return result


if __name__ == '__main__':
    import unittest

    import mock_sublime
    
    def node_text(node):
        return node.view.substr(node.region)

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
            self.assertEqual(node_text(result.children[0].children[0]), " - some list item")
            self.assertEqual(node_text(result.children[0].children[1]), " - another list item")

        def test_simple_list(self):
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
            self.assertEqual(node_text(result.children[0].children[0]), " - parent 1\n   - child")
            self.assertEqual(len(result.children[0].children[0].children), 1)
            self.assertEqual(node_text(result.children[0].children[0].children[0]), "   - child")
            self.assertEqual(node_text(result.children[0].children[1]), " - parent 2")

    unittest.main()
