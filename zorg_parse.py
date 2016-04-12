# -*- coding: utf-8 -*-

import re

# TODO: вынести регулярки в начало, чтобы компилировались 1 раз
# TODO: все тэги, ключевые слова и прочее должны быть своими нодами, чтобы у них были begin/end

# formal grammar

# HEADLINE: STARS KEYWORD? PRIORITY? TEXT TAGS?

def parse_org_string(text):
    p = Parser(text)
    return p.parse_org_document()

def _iter_subsection(node):
    for subsection in node.subsection_list:
        yield subsection
        for subsubsection in _iter_subsection(subsection):
            yield subsubsection


class Parser(object):
    keyword_set = frozenset(['TODO', 'DONE'])

    def __init__(self, text):
        self._current_line_begin = [0]
        self._current_line_end = [0]
        self._current_line = [None]
        self._line_iter = iter(text.split('\n'))
        self._next_line()
        self._document = OrgDocument(text)

    def get_current_line(self):
        return self._current_line[-1]

    def get_current_line_begin(self):
        return self._current_line_begin[-1]

    def get_current_line_end(self):
        return self._current_line_end[-1]

    def _next_line(self):
        assert len(self._current_line) == 1
        self._current_line_begin[0] = self._current_line_end[0]
        try:
            self._current_line[0] = next(self._line_iter)
            self._current_line_end[0] = self._current_line_begin[0] + len(self._current_line[0]) + 1
        except StopIteration:
            self._current_line = None
            self._current_line_end[0] = self._current_line_begin[0]
            # TODO: если в последней строке не было \n, то у нас она должна быть короче

    def _is_exhausted(self):
        return self._current_line is None

    def _push_context(self, line, begin, end):
        self._current_line.append(line)
        self._current_line_begin.append(begin)
        self._current_line_end.append(end)

    def _push_context_substr(self, begin, end):
        return self._push_context(self.get_current_line()[begin:end],
                                 self.get_current_line_begin() + begin,
                                 self.get_current_line_begin() + end)

    def _pop_context(self):
        self._current_line.pop()
        self._current_line_begin.pop()
        self._current_line_end.pop()

    def parse_org_document(self):
        section_stack = [self._document]
        while not self._is_exhausted():
            headline = self.consume_headline()
            if headline:
                assert headline.level > 0
                while headline.level < section_stack[-1].level:
                    section_stack.pop()
                section_stack.append(section_stack[-1].add_subsection_from_headline(headline))
                continue
            inner_section = self.consume_inner_section()
            assert inner_section is not None
            assert section_stack[-1].inner_section is None
            section_stack[-1].inner_section = inner_section
        return self._document

    def consume_inner_section(self):
        result = None
        while not self._is_exhausted() and not self.is_header():
            if result is None:
                result = TextNode(self._document, self.get_current_line_begin(), self.get_current_line_end(), [])
            else:
                result.merge(self.get_current_line_begin(), self.get_current_line_end(), [])
            self._next_line()
        return result

    def consume_headline(self):
        result = self.try_parse_headline()
        if result is not None:
            self._next_line()
        return result

    def is_header(self):
        line = self.get_current_line()
        match = re.match('^[*]+\s.*$', line)
        return bool(match)

    def try_parse_headline(self):
        line = self.get_current_line()
        match = re.match('^([*]+) \s+'  # STARS group 1
                         '(?: ([A-Za-z0-9]+) \s+ )?' # KEYWORD group 2
                         '(?:\[[#]([a-zA-Z])\]\s+)?' # PRIORITY group 3
                         '(.*?)' # TITLE -- match in nongreedy fashion group 4
                         '\s*( : (?: [a-zA-Z0-9_@#]+: )+ )?\s*$', # TAGS group 5
                         line, re.VERBOSE)
        if not match:
            return None

        # понять уровень заголовка
        headline_level = len(match.group(1))

        # понять есть ли ключевое слово
        if match.group(2) is not None and match.group(2) in self.keyword_set:
            keyword = match.group(2)
        else:
            keyword = None

        title_begin = match.start(4)
        title_end = match.end(4)
        if match.group(2) is not None and keyword is None:
            # there is some word before priority
            priority = None
            title_begin = match.start(2)
        elif match.group(3) is None:
            priority = None
        else:
            priority = match.group(3)

        tag_group = match.group(5)
        if tag_group is not None:
            tags = tag_group.strip(':').split(':')
        else:
            tags = []

        self._push_context_substr(title_begin, title_end)
        title_node = self.parse_text_node()
        self._pop_context()

        return OrgHeadline(
            document=self._document,
            begin=self.get_current_line_begin(),
            end=self.get_current_line_end(),
            level=headline_level,
            title=title_node,
            tags=tags,
            keyword=keyword,
            priority=priority)

    def parse_text_node(self):
        return TextNode(self._document, self.get_current_line_begin(), self.get_current_line_end(), [])
    

class OrgNode(object):
    def __init__(self, document, begin, end):
        self.document = document
        self.begin = begin
        self.end = end

    def get_text(self):
        return self.document.text[self.begin:self.end]

class TextNode(OrgNode):
    def __init__(self, document, begin, end, links):
        super(TextNode, self).__init__(document, begin, end)
        self.links = links

    def merge(self, begin, end, links):
        if begin != self.end:
            raise ValueError("sections should be consequtive; old end: {} new begin: {}".format(self.end, begin))
        self.end = end
        self.links += links

class OrgDocument(object):
    def __init__(self, text):
        self.headline = None
        self.level = 0
        self.inner_section = None
        self.text = text
        self.subsection_list = []

    def add_subsection_from_headline(self, headline):
        subsection = OrgSection.from_headline(self, headline)
        self.subsection_list.append(subsection)
        return subsection

    def iter_section(self):
        return _iter_subsection(self)

class OrgSection(OrgNode):
    def __init__(self, document, begin, end, headline, inner_section):
        super(OrgSection, self).__init__(document, begin, end)
        self.headline = headline
        self.level = headline.level
        self.inner_section = inner_section
        self.subsection_list = []

    def add_subsection_from_headline(self, headline):
        if self.document is not headline.document:
            raise ValueError
        subsection = OrgSection.from_headline(self.document, headline)
        self.subsection_list.append(subsection)
        return subsection

    @classmethod
    def from_headline(cls, document, headline):
        return OrgSection(document, headline.begin, headline.end, headline, None)


class OrgHeadline(OrgNode):
    def __init__(self, document, begin, end, level, title, tags, keyword, priority):
        super(OrgHeadline, self).__init__(document, begin, end)
        self.level = level
        self.title = title
        self.tags = tags
        self.keyword = keyword
        self.priority = priority

if __name__ == '__main__':
    import unittest

    class TestHeadlineParsing(unittest.TestCase):
        def test_simple_header_parsing(self):
            p = Parser('** foo')
            headline = p.try_parse_headline()
            self.assertEqual(headline.level, 2)

            p = Parser('*foo')
            headline = p.try_parse_headline()
            self.assertEqual(headline, None)

        def test_tags_parsing(self):
            p = Parser('** foo :tag1:tag2:')
            headline = p.try_parse_headline()
            self.assertEqual(headline.tags, ['tag1', 'tag2'])

        def test_title_parsing(self):
            p = Parser('** some text')
            headline = p.try_parse_headline()
            self.assertEqual(headline.title.get_text(), "some text")

            p = Parser('* TODO some text')
            headline = p.try_parse_headline()
            self.assertEqual(headline.title.get_text(), "some text")

            p = Parser('*** TODO [#a] some text')
            headline = p.try_parse_headline()
            self.assertEqual(headline.title.get_text(), "some text")

            p = Parser('*** TODO [#a] some text :tag1:tag2:')
            headline = p.try_parse_headline()
            self.assertEqual(headline.title.get_text(), "some text")

    def print_structure(node):
        if node is None:
            return "None"
        elif isinstance(node, OrgDocument) or isinstance(node, OrgSection):
            if isinstance(node, OrgDocument):
                maybelevel = ''
                name = 'OrgDocument'
            else:
                name = "OrgSection"
                maybelevel = " {}".format(node.level)
            return "({name}{maybelevel} {inner_section} [{subsection_list}])".format(
                name=name,
                maybelevel=maybelevel,
                inner_section=print_structure(node.inner_section),
                subsection_list=' '.join(print_structure(n) for n in node.subsection_list))
        elif isinstance(node, TextNode):
            return "(TextNode)"
        else:
            raise ValueError("Unknown node type: {}".format(node.__class__))

    class TestDocumentParsing(unittest.TestCase):
        def test_simple_parsing(self):
            document = parse_org_string('some text\n'
                                        '* Some header\n'
                                        'more text\n')
            self.assertEqual(print_structure(document),
                             "(OrgDocument (TextNode) [(OrgSection 1 (TextNode) [])])")

        def test_parsing_with_subsections(self):
            document = parse_org_string('** Header 1\n'
                                        '* Header 2\n'
                                        '*** Header 3\n'
                                        '** Header 4\n'
                                        '*** Header 5\n')
            self.assertEqual(print_structure(document),
                             "(OrgDocument None ["
                                 "(OrgSection 2 None []) "
                                 "(OrgSection 1 None ["
                                     "(OrgSection 3 None []) "
                                     "(OrgSection 2 None ["
                                         "(OrgSection 3 (TextNode) [])"
                                     "])"
                                 "])"
                             "])")

    class TestIterSubsection(unittest.TestCase):
        def test_simple(self):
            document = parse_org_string('** Header 1\n'
                                        '* Header 2\n'
                                        '*** Header 3\n'
                                        '** Header 4\n'
                                        '*** Header 5\n')
            subsections = [s.headline.title.get_text() for s in document.iter_section()]
            self.assertEqual(
                subsections,
                ["Header 1", "Header 2", "Header 3", "Header 4", "Header 5"])

    unittest.main()
