"""Decide whether two case-sensitive glob patterns have a common match.

The accepted syntax intentionally follows :func:`fnmatch.fnmatchcase`:

* ``?`` matches exactly one arbitrary Unicode character;
* ``*`` matches any number of arbitrary Unicode characters;
* ``[abc]`` and ``[a-z]`` match character classes;
* ``[!abc]`` negates a character class;
* an unclosed ``[`` is a literal ``[``;
* there is no backslash escape syntax (wrap metacharacters in ``[]``);
* path separators are ordinary characters, and ``**`` is equivalent to ``*``.

The implementation compiles each pattern into a small epsilon-NFA, then checks
reachability in the product of the two automata.  It never enumerates candidate
strings.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import sys
from typing import Final, TypeAlias


_MAX_CODE_POINT: Final = sys.maxunicode
_Interval: TypeAlias = tuple[int, int]


@dataclass(frozen=True, slots=True)
class _CharSet:
    """A normalized union of closed Unicode code-point intervals."""

    intervals: tuple[_Interval, ...]

    @classmethod
    def from_intervals(cls, intervals: list[_Interval]) -> _CharSet:
        if not intervals:
            return cls(())

        intervals.sort()
        merged: list[_Interval] = []
        start, end = intervals[0]

        for next_start, next_end in intervals[1:]:
            if next_start <= end + 1:
                end = max(end, next_end)
            else:
                merged.append((start, end))
                start, end = next_start, next_end

        merged.append((start, end))
        return cls(tuple(merged))

    @classmethod
    def literal(cls, character: str) -> _CharSet:
        code_point = ord(character)
        return cls(((code_point, code_point),))

    def complement(self) -> _CharSet:
        complement: list[_Interval] = []
        next_start = 0

        for start, end in self.intervals:
            if next_start < start:
                complement.append((next_start, start - 1))
            next_start = end + 1

        if next_start <= _MAX_CODE_POINT:
            complement.append((next_start, _MAX_CODE_POINT))

        return _CharSet(tuple(complement))

    def intersects(self, other: _CharSet) -> bool:
        """Return whether the two normalized interval unions overlap."""

        left = right = 0
        while left < len(self.intervals) and right < len(other.intervals):
            left_start, left_end = self.intervals[left]
            right_start, right_end = other.intervals[right]

            if left_end < right_start:
                left += 1
            elif right_end < left_start:
                right += 1
            else:
                return True

        return False


_ANY: Final = _CharSet(((0, _MAX_CODE_POINT),))


@dataclass(frozen=True, slots=True)
class _Token:
    # None denotes ``*``.  Every other token consumes exactly one character.
    charset: _CharSet | None

    @property
    def is_star(self) -> bool:
        return self.charset is None


_STAR: Final = _Token(None)
_ANY_ONE: Final = _Token(_ANY)


def _class_charset(body: str) -> _CharSet:
    """Compile the non-negated body of a fnmatch-style character class.

    The chunking mirrors CPython's handling of hyphens, including ignored
    descending ranges such as ``[z-a]`` and literal trailing hyphens.
    """

    chunks: list[str] = []
    chunk_start = 0
    search_start = 1

    while True:
        hyphen = body.find("-", search_start)
        if hyphen < 0:
            break
        chunks.append(body[chunk_start:hyphen])
        chunk_start = hyphen + 1
        # Skip the range end and the following character.  This prevents
        # overlapping constructs such as a-c-e from becoming two ranges.
        search_start = hyphen + 3

    tail = body[chunk_start:]
    if tail:
        chunks.append(tail)
    elif chunks:
        chunks[-1] += "-"

    # Remove descending ranges exactly as fnmatch.translate does.
    for index in range(len(chunks) - 1, 0, -1):
        if chunks[index - 1][-1] > chunks[index][0]:
            chunks[index - 1] = chunks[index - 1][:-1] + chunks[index][1:]
            del chunks[index]

    if not chunks or not chunks[0]:
        return _CharSet(())

    intervals: list[_Interval] = []

    for chunk in chunks:
        intervals.extend((ord(character), ord(character)) for character in chunk)

    for left, right in zip(chunks, chunks[1:]):
        intervals.append((ord(left[-1]), ord(right[0])))

    return _CharSet.from_intervals(intervals)


def _parse_class(pattern: str, open_index: int) -> tuple[_CharSet, int] | None:
    """Parse ``pattern[open_index:]`` or return None for an unclosed class."""

    length = len(pattern)
    content_start = open_index + 1
    close_index = content_start

    if close_index < length and pattern[close_index] == "!":
        close_index += 1
    if close_index < length and pattern[close_index] == "]":
        close_index += 1

    while close_index < length and pattern[close_index] != "]":
        close_index += 1

    if close_index >= length:
        return None

    body = pattern[content_start:close_index]
    negated = body.startswith("!")
    if negated:
        body = body[1:]

    charset = _class_charset(body)
    if negated:
        charset = charset.complement()

    return charset, close_index + 1


def _compile(pattern: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    index = 0

    while index < len(pattern):
        character = pattern[index]

        if character == "*":
            if not tokens or not tokens[-1].is_star:
                tokens.append(_STAR)
            index += 1
        elif character == "?":
            tokens.append(_ANY_ONE)
            index += 1
        elif character == "[":
            parsed = _parse_class(pattern, index)
            if parsed is None:
                tokens.append(_Token(_CharSet.literal("[")))
                index += 1
            else:
                charset, index = parsed
                tokens.append(_Token(charset))
        else:
            tokens.append(_Token(_CharSet.literal(character)))
            index += 1

    return tuple(tokens)


def glob_intersects(pattern1: str, pattern2: str) -> bool:
    """Return whether two case-sensitive glob patterns share any matched string.

    Args:
        pattern1: First fnmatch-style glob pattern.
        pattern2: Second fnmatch-style glob pattern.

    Returns:
        ``True`` if at least one Unicode string matches both patterns.

    Raises:
        TypeError: If either argument is not a string.

    Complexity:
        Let ``m`` and ``n`` be the pattern lengths.  Product-automaton
        reachability takes ``O(m * n)`` time and memory in the worst case.
        Character-class normalization adds at most
        ``O(m log m + n log n)`` preprocessing time.
    """

    if not isinstance(pattern1, str) or not isinstance(pattern2, str):
        raise TypeError("pattern1 and pattern2 must both be str objects")

    left_tokens = _compile(pattern1)
    right_tokens = _compile(pattern2)
    left_length = len(left_tokens)
    right_length = len(right_tokens)

    start = (0, 0)
    pending = deque([start])
    visited = {start}

    def enqueue(state: tuple[int, int]) -> None:
        if state not in visited:
            visited.add(state)
            pending.append(state)

    while pending:
        left_index, right_index = pending.popleft()

        if left_index == left_length and right_index == right_length:
            return True

        left_token = (
            left_tokens[left_index] if left_index < left_length else None
        )
        right_token = (
            right_tokens[right_index] if right_index < right_length else None
        )

        # A star may consume nothing (epsilon transition).
        if left_token is not None and left_token.is_star:
            enqueue((left_index + 1, right_index))
        if right_token is not None and right_token.is_star:
            enqueue((left_index, right_index + 1))

        if left_token is None or right_token is None:
            continue

        left_charset = _ANY if left_token.is_star else left_token.charset
        right_charset = _ANY if right_token.is_star else right_token.charset
        assert left_charset is not None and right_charset is not None

        # Both automata consume the same next character.  A star stays on its
        # state; a one-character token advances.
        if left_charset.intersects(right_charset):
            enqueue(
                (
                    left_index if left_token.is_star else left_index + 1,
                    right_index if right_token.is_star else right_index + 1,
                )
            )

    return False
