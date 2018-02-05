# -*- coding: utf-8 -*-
"""
Checks for got-vs-want statments
"""
from __future__ import print_function, division, absolute_import, unicode_literals
import re
import difflib
from xdoctest import utils
from xdoctest import constants
from xdoctest import directive

unicode_literal_re = re.compile(r"(\W|^)[uU]([rR]?[\'\"])", re.UNICODE)  # nocover
bytes_literal_re = re.compile(r"(\W|^)[bB]([rR]?[\'\"])", re.UNICODE)  # nocover

BLANKLINE_MARKER = '<BLANKLINE>'  # nocover
ELLIPSIS_MARKER = '...'  # nocover

TRAILING_WS = re.compile(r"[ \t]*$", re.UNICODE | re.MULTILINE)  # nocover


_EXCEPTION_RE = re.compile(r"""
    # Grab the traceback header.  Different versions of Python have
    # said different things on the first traceback line.
    ^(?P<hdr> Traceback\ \(
        (?: most\ recent\ call\ last
        |   innermost\ last
        ) \) :
    )
    \s* $                # toss trailing whitespace on the header.
    (?P<stack> .*?)      # don't blink: absorb stuff until...
    ^ (?P<msg> \w+ .*)   #     a line *starts* with alphanum.
    """, re.VERBOSE | re.MULTILINE | re.DOTALL)


def check_got_vs_want(want, got_stdout, got_eval=constants.NOT_EVALED,
                      runstate=None):
    """
    Determines to check against either got_stdout or got_eval, and then does
    the comparison.

    If both stdout and eval "got" outputs are specified, then the "want"
    target may match either value.

    Args:
        want (str): target to match against
        got_stdout (str): output from stdout
        got_eval (str): output from an eval statement.

    Raises:
        GotWantException - If the "got" differs from this parts want.
    """
    # If we did not want anything than ignore eval and stdout
    if got_eval is constants.NOT_EVALED:
        # if there was no eval, check stdout
        got = got_stdout
        flag = check_output(got, want, runstate)
    else:
        if not got_stdout:
            # If there was no stdout then use eval value.
            got = repr(got_eval)
            flag = check_output(got, want, runstate)
        else:
            # If there was eval and stdout, defer to stdout
            # but allow fallback on the eval.
            got = got_stdout
            flag = check_output(got, want, runstate)
            if not flag:
                # allow eval to fallback and save us, but if it fails, do a
                # diff with stdout
                got = repr(got_eval)
                flag = check_output(got, want, runstate)
                if not flag:
                    got = got_stdout
    if not flag:
        msg = 'got differs with doctest want'
        ex = GotWantException(msg, got, want)
        # print(ex.output_difference(runstate))
        raise ex
    return flag


def _strip_exception_details(msg):
    # Support for IGNORE_EXCEPTION_DETAIL.
    # Get rid of everything except the exception name; in particular, drop
    # the possibly dotted module path (if any) and the exception message (if
    # any).  We assume that a colon is never part of a dotted name, or of an
    # exception name.
    # E.g., given
    #    "foo.bar.MyError: la di da"
    # return "MyError"
    # Or for "abc.def" or "abc.def:\n" return "def".

    start, end = 0, len(msg)
    # The exception name must appear on the first line.
    i = msg.find("\n")
    if i >= 0:
        end = i
    # retain up to the first colon (if any)
    i = msg.find(':', 0, end)
    if i >= 0:
        end = i
    # retain just the exception name
    i = msg.rfind('.', 0, end)
    if i >= 0:
        start = i + 1
    return msg[start: end]


def check_exception(exc_got, want, runstate=None):
    """
    Checks want against an exception

    Raises:
        GotWantException - If the "got" differs from this parts want.
    """
    m = _EXCEPTION_RE.match(want)
    exc_want = m.group('msg') if m else None
    if exc_want is None:
        raise
    flag = check_output(exc_got, exc_want, runstate)
    # print('exc_want = {!r}'.format(exc_want))
    # print('exc_got = {!r}'.format(exc_got))
    # print('flag = {!r}'.format(flag))

    if not flag and runstate['IGNORE_EXCEPTION_DETAIL']:
        exc_got1 = _strip_exception_details(exc_got)
        exc_want1 = _strip_exception_details(exc_want)
        flag = check_output(exc_got1, exc_want1, runstate)
        if flag:
            exc_got = exc_got1
            exc_want = exc_want1

    if not flag:
        msg = 'exception message is different'
        ex = GotWantException(msg, exc_got, exc_want)
        # print(ex.output_difference(runstate))
        raise ex
    return flag


def check_output(got, want, runstate=None):
    """
    Does the actual comparison between `got` and `want`
    """
    if not want:  # nocover
        return True
    if want:
        # Try default
        if got == want:
            return True

        got, want = normalize(got, want, runstate)
        if got == want:
            return True

        if runstate['ELLIPSIS']:
            if _ellipsis_match(got, want):
                return True
    return False


def _ellipsis_match(got, want):
    """
    The ellipsis matching algorithm taken directly from standard doctest.

    Worst-case linear-time ellipsis matching.

    CommandLine:
        python -m xdoctest.checker _ellipsis_match

    Example:
        >>> _ellipsis_match('aaa', 'aa...aa')
        False
        >>> _ellipsis_match('anything', '...')
        True
        >>> _ellipsis_match('prefix-anything', 'prefix-...')
        True
        >>> _ellipsis_match('suffix-anything', 'prefix-...')
        False
        >>> _ellipsis_match('foo', '... foo')
        True
    """
    if ELLIPSIS_MARKER not in want:
        return want == got

    # Find "the real" strings.
    # ws = want.split(ELLIPSIS_MARKER)
    # MODIFICATION: the ellipsis consumes all whitespace around it
    # for compatibility with whitespace normalization.
    ws = re.split('\s*{}\s*'.format(re.escape(ELLIPSIS_MARKER)), want,
                  flags=re.MULTILINE)
    assert len(ws) >= 2

    # Deal with exact matches possibly needed at one or both ends.
    startpos, endpos = 0, len(got)
    w = ws[0]
    if w:   # starts with exact match
        if got.startswith(w):
            startpos = len(w)
            del ws[0]
        else:
            return False
    w = ws[-1]
    if w:   # ends with exact match
        if got.endswith(w):
            endpos -= len(w)
            del ws[-1]
        else:
            return False

    if startpos > endpos:
        # Exact end matches required more characters than we have, as in
        # _ellipsis_match('aa...aa', 'aaa')
        return False

    # For the rest, we only need to find the leftmost non-overlapping
    # match for each piece.  If there's no overall match that way alone,
    # there's no overall match period.
    for w in ws:
        # w may be '' at times, if there are consecutive ellipses, or
        # due to an ellipsis at the start or end of `want`.  That's OK.
        # Search for an empty string succeeds, and doesn't change startpos.
        startpos = got.find(w, startpos, endpos)
        if startpos < 0:
            return False
        startpos += len(w)

    return True


def normalize(got, want, runstate=None):
    r"""
    Adapated from doctest_nose_plugin.py from the nltk project:
        https://github.com/nltk/nltk

    Further extended to also support byte literals.

    Example:
        >>> want = "...\n(0, 2, {'weight': 1})\n(0, 3, {'weight': 2})"
        >>> got = "(0, 2, {'weight': 1})\n(0, 3, {'weight': 2})"
    """
    if runstate is None:
        runstate = directive.RuntimeState()

    def remove_prefixes(regex, text):
        return re.sub(regex, r'\1\2', text)

    def visible_text(lines):
        # TODO: backspaces
        # Any lines that end with only a carrage return are erased
        return [line for line in lines if not line.endswith('\r')]

    # Remove terminal colors
    if True:
        got = utils.strip_ansi(got)
        want = utils.strip_ansi(want)

    # normalize python 2/3 byte/unicode prefixes
    if True:
        got = remove_prefixes(unicode_literal_re, got)
        want = remove_prefixes(unicode_literal_re, want)

        got = remove_prefixes(bytes_literal_re, got)
        want = remove_prefixes(bytes_literal_re, want)

    # always remove trailing whitepsace
    got = re.sub(TRAILING_WS, '', got)
    want = re.sub(TRAILING_WS, '', want)
    # normalize endling newlines
    want = want.rstrip()
    got = got.rstrip()

    # Always remove invisible text
    got_lines = got.splitlines(True)
    want_lines = want.splitlines(True)
    got_lines = visible_text(got_lines)
    want_lines = visible_text(want_lines)
    want = ''.join(want_lines)
    got = ''.join(got_lines)

    if runstate['NORMALIZE_WHITESPACE'] or runstate['IGNORE_WHITESPACE']:

        # all whitespace normalization
        # treat newlines and all whitespace as a single space
        got = ' '.join(got.split())
        want = ' '.join(want.split())

    if runstate['IGNORE_WHITESPACE']:
        # Completely remove whitespace
        got = re.sub('\s', '', got, flags=re.MULTILINE)
        want = re.sub('\s', '', want, flags=re.MULTILINE)
    return got, want


class GotWantException(AssertionError):
    def __init__(self, msg, got, want):
        super(GotWantException, self).__init__(msg)
        self.got = got
        self.want = want

    def _do_a_fancy_diff(self, runstate=None):
        # Not unless they asked for a fancy diff.
        got = self.got
        want = self.want

        if runstate is None:
            runstate = directive.RuntimeState()

        # ndiff does intraline difference marking, so can be useful even
        # for 1-line differences.
        if runstate['REPORT_NDIFF']:
            return True

        # The other diff types need at least a few lines to be helpful.
        if runstate['REPORT_UDIFF'] or runstate['REPORT_CDIFF']:
            return want.count('\n') > 2 and got.count('\n') > 2

        return False

    def output_difference(self, runstate=None, colored=True):
        """
        Return a string describing the differences between the expected output
        for a given example (`example`) and the actual output (`got`).
        The `runstate` contains option flags used to compare `want` and `got`.
        """
        got = self.got
        want = self.want

        if runstate is None:
            runstate = directive.RuntimeState()

        got, want = normalize(got, want, runstate)

        # If <BLANKLINE>s are being used, then replace blank lines
        # with <BLANKLINE> in the actual output string.
        if not runstate['DONT_ACCEPT_BLANKLINE']:
            got = re.sub('(?m)^[ ]*(?=\n)', BLANKLINE_MARKER, got)

        got = utils.ensure_unicode(got)

        # Check if we should use diff.
        if self._do_a_fancy_diff(runstate):
            # Split want & got into lines.
            want_lines = want.splitlines(True)
            got_lines = got.splitlines(True)
            # Use difflib to find their differences.
            if runstate['REPORT_UDIFF']:
                diff = difflib.unified_diff(want_lines, got_lines, n=2)
                diff = list(diff)[2:]  # strip the diff header
                kind = 'unified diff with -expected +actual'
            elif runstate['REPORT_CDIFF']:
                diff = difflib.context_diff(want_lines, got_lines, n=2)
                diff = list(diff)[2:]  # strip the diff header
                kind = 'context diff with expected followed by actual'
            elif runstate['REPORT_NDIFF']:
                engine = difflib.Differ(charjunk=difflib.IS_CHARACTER_JUNK)
                diff = list(engine.compare(want_lines, got_lines))
                kind = 'ndiff with -expected +actual'
            else:
                raise ValueError('Invalid difflib option')

            # Remove trailing whitespace on diff output.
            diff = [line.rstrip() + '\n' for line in diff]
            diff_text = ''.join(diff)
            if colored:
                diff_text = utils.highlight_code(diff_text, lexer_name='diff')

            text = 'Differences (%s):\n' % kind + utils.indent(diff_text)
        else:
            # If we're not using diff, then simply list the expected
            # output followed by the actual output.
            if want and got:
                if colored:
                    got = utils.color_text(got, 'red')
                    want = utils.color_text(want, 'red')
                text = 'Expected:\n%s\nGot:\n%s' % (
                    utils.indent(want), utils.indent(got))
            elif want:
                if colored:
                    got = utils.color_text(got, 'red')
                    want = utils.color_text(want, 'red')
                text = 'Expected:\n%s\nGot nothing\n' % utils.indent(want)
            elif got:  # nocover
                raise AssertionError('impossible state')
                text = 'Expected nothing\nGot:\n%s' % utils.indent(got)
            else:  # nocover
                raise AssertionError('impossible state')
                text = 'Expected nothing\nGot nothing\n'
        return text


if __name__ == '__main__':
    """
    CommandLine:
        python -m xdoctest.checker all
    """
    import xdoctest as xdoc
    xdoc.doctest_module()
