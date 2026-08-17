"""Boolean set-algebra decisions for two case-sensitive glob patterns.

The accepted syntax intentionally follows :func:`fnmatch.fnmatchcase`:

* ``?`` matches exactly one arbitrary Unicode character;
* ``*`` matches any number of arbitrary Unicode characters;
* ``[abc]`` and ``[a-z]`` match character classes;
* ``[!abc]`` negates a character class;
* an unclosed ``[`` is a literal ``[``;
* there is no backslash escape syntax (wrap metacharacters in ``[]``);
* path separators are ordinary characters, and ``**`` is equivalent to ``*``.

Each pattern denotes a language (a set of strings) over the Unicode alphabet.
The four mutually exclusive Venn regions represented by :class:`GlobRegion`
form a complete basis for every binary Boolean set operation.  The public API
only answers Boolean questions; it never tries to convert a union, difference,
or complement back into glob syntax, which is not closed under those operations.

Plain intersection uses direct epsilon-NFA product reachability.  Operations
that involve complement use lazy subset construction and explore only the DFA
states needed by the query.  Neither algorithm enumerates candidate strings.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import deque
from dataclasses import dataclass
from enum import IntFlag
import sys
from typing import Final, TypeAlias


_MAX_CODE_POINT: Final = sys.maxunicode
_Interval: TypeAlias = tuple[int, int]
_DfaState: TypeAlias = frozenset[int]


class GlobRegion(IntFlag):
    """Membership regions for two glob languages ``LEFT`` and ``RIGHT``.

    Any combination of these four disjoint regions describes one of the 16
    possible binary Boolean set operations.  Common combinations are provided
    as aliases for readability.
    """

    EMPTY = 0

    NEITHER = 1 << 0
    RIGHT_ONLY = 1 << 1
    LEFT_ONLY = 1 << 2
    BOTH = 1 << 3

    NOT_LEFT = NEITHER | RIGHT_ONLY
    NOT_RIGHT = NEITHER | LEFT_ONLY
    LEFT = LEFT_ONLY | BOTH
    RIGHT = RIGHT_ONLY | BOTH
    SYMMETRIC_DIFFERENCE = LEFT_ONLY | RIGHT_ONLY
    UNION = RIGHT_ONLY | LEFT_ONLY | BOTH
    UNIVERSE = NEITHER | RIGHT_ONLY | LEFT_ONLY | BOTH


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

    def contains(self, code_point: int) -> bool:
        """Return whether a code point belongs to this interval union."""

        index = bisect_right(
            self.intervals,
            (code_point, _MAX_CODE_POINT),
        ) - 1
        return index >= 0 and code_point <= self.intervals[index][1]


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


def _validate_patterns(pattern1: str, pattern2: str) -> None:
    if not isinstance(pattern1, str) or not isinstance(pattern2, str):
        raise TypeError("pattern1 and pattern2 must both be str objects")


def _tokens_intersect(
    left_tokens: tuple[_Token, ...],
    right_tokens: tuple[_Token, ...],
) -> bool:
    """Check positive intersection directly on two epsilon-NFAs."""

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


def _tokens_nonempty(tokens: tuple[_Token, ...]) -> bool:
    """Return whether a single glob NFA accepts at least one string."""

    return all(
        token.charset is None or bool(token.charset.intervals)
        for token in tokens
    )


def _epsilon_closure(
    tokens: tuple[_Token, ...],
    states: set[int] | frozenset[int],
) -> _DfaState:
    """Follow every zero-character star transition from NFA states."""

    closure = set(states)
    pending = list(states)

    while pending:
        state = pending.pop()
        if state < len(tokens) and tokens[state].is_star:
            next_state = state + 1
            if next_state not in closure:
                closure.add(next_state)
                pending.append(next_state)

    return frozenset(closure)


def _dfa_transition(
    tokens: tuple[_Token, ...],
    state: _DfaState,
    code_point: int,
) -> _DfaState:
    """Lazily compute one determinized transition."""

    destinations: set[int] = set()

    for position in state:
        if position == len(tokens):
            continue

        token = tokens[position]
        if token.is_star:
            destinations.add(position)
        else:
            assert token.charset is not None
            if token.charset.contains(code_point):
                destinations.add(position + 1)

    return _epsilon_closure(tokens, destinations)


def _alphabet_representatives(
    left_tokens: tuple[_Token, ...],
    right_tokens: tuple[_Token, ...],
) -> tuple[int, ...]:
    """Partition Unicode into atoms with identical token behavior."""

    boundaries = {0, _MAX_CODE_POINT + 1}

    for tokens in (left_tokens, right_tokens):
        for token in tokens:
            if token.charset is None:
                continue
            for start, end in token.charset.intervals:
                boundaries.add(start)
                boundaries.add(end + 1)

    ordered = sorted(boundaries)
    return tuple(ordered[:-1])


def _boolean_operation_nonempty(
    left_tokens: tuple[_Token, ...],
    right_tokens: tuple[_Token, ...],
    region_mask: int,
) -> bool:
    """Test non-emptiness of an arbitrary two-language Boolean operation."""

    if region_mask == GlobRegion.EMPTY:
        return False
    if region_mask == GlobRegion.UNIVERSE:
        # The universe contains at least the empty string.
        return True
    if region_mask == GlobRegion.BOTH:
        # Preserve the polynomial fast path for the overwhelmingly common
        # positive-intersection query.
        return _tokens_intersect(left_tokens, right_tokens)
    if region_mask == GlobRegion.LEFT:
        return _tokens_nonempty(left_tokens)
    if region_mask == GlobRegion.RIGHT:
        return _tokens_nonempty(right_tokens)
    if region_mask == GlobRegion.UNION:
        return _tokens_nonempty(left_tokens) or _tokens_nonempty(right_tokens)

    representatives = _alphabet_representatives(left_tokens, right_tokens)
    left_start = _epsilon_closure(left_tokens, {0})
    right_start = _epsilon_closure(right_tokens, {0})
    start = (left_start, right_start)

    pending = deque([start])
    visited = {start}
    left_transition_cache: dict[_DfaState, tuple[_DfaState, ...]] = {}
    right_transition_cache: dict[_DfaState, tuple[_DfaState, ...]] = {}

    def transitions(
        tokens: tuple[_Token, ...],
        state: _DfaState,
        cache: dict[_DfaState, tuple[_DfaState, ...]],
    ) -> tuple[_DfaState, ...]:
        result = cache.get(state)
        if result is None:
            result = tuple(
                _dfa_transition(tokens, state, code_point)
                for code_point in representatives
            )
            cache[state] = result
        return result

    while pending:
        left_state, right_state = pending.popleft()
        left_accepts = len(left_tokens) in left_state
        right_accepts = len(right_tokens) in right_state
        membership_case = (int(left_accepts) << 1) | int(right_accepts)

        if region_mask & (1 << membership_case):
            return True

        left_destinations = transitions(
            left_tokens,
            left_state,
            left_transition_cache,
        )
        right_destinations = transitions(
            right_tokens,
            right_state,
            right_transition_cache,
        )

        for destination in zip(left_destinations, right_destinations):
            if destination not in visited:
                visited.add(destination)
                pending.append(destination)

    return False


def glob_operation_nonempty(
    pattern1: str,
    pattern2: str,
    regions: GlobRegion,
) -> bool:
    """Return whether a Boolean set operation on two globs is non-empty.

    ``regions`` selects any union of the four disjoint membership regions.  It
    therefore represents all 16 binary Boolean operations over the languages
    denoted by ``pattern1`` and ``pattern2``.

    Examples:
        ``GlobRegion.BOTH`` represents intersection.
        ``GlobRegion.UNION`` represents union.
        ``GlobRegion.LEFT_ONLY`` represents ``pattern1 - pattern2``.
        ``GlobRegion.SYMMETRIC_DIFFERENCE`` represents symmetric difference.
        ``GlobRegion.NOT_LEFT`` represents the complement of ``pattern1``.

    Args:
        pattern1: Left fnmatch-style glob pattern.
        pattern2: Right fnmatch-style glob pattern.
        regions: The result regions whose union should be tested.

    Returns:
        ``True`` if the selected Boolean operation contains at least one string.

    Raises:
        TypeError: If the patterns are not strings or ``regions`` is not a
            :class:`GlobRegion`.

    Complexity:
        Positive intersection retains ``O(m * n)`` worst-case time and memory.
        Operations involving complement use lazy NFA determinization.  They
        only visit reachable subset states, but their theoretical worst case is
        exponential in the combined pattern length.
    """

    _validate_patterns(pattern1, pattern2)
    if not isinstance(regions, GlobRegion):
        raise TypeError("regions must be a GlobRegion value")
    if int(regions) & ~int(GlobRegion.UNIVERSE):
        raise ValueError("regions contains bits outside the four GlobRegion cases")

    return _boolean_operation_nonempty(
        _compile(pattern1),
        _compile(pattern2),
        int(regions),
    )


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

    _validate_patterns(pattern1, pattern2)
    return _tokens_intersect(_compile(pattern1), _compile(pattern2))


def glob_is_disjoint(pattern1: str, pattern2: str) -> bool:
    """Return whether the two glob languages have an empty intersection."""

    return not glob_intersects(pattern1, pattern2)


def glob_is_subset(pattern1: str, pattern2: str) -> bool:
    """Return whether every match of ``pattern1`` also matches ``pattern2``."""

    return not glob_operation_nonempty(
        pattern1,
        pattern2,
        GlobRegion.LEFT_ONLY,
    )


def glob_is_superset(pattern1: str, pattern2: str) -> bool:
    """Return whether every match of ``pattern2`` also matches ``pattern1``."""

    return not glob_operation_nonempty(
        pattern1,
        pattern2,
        GlobRegion.RIGHT_ONLY,
    )


def glob_equivalent(pattern1: str, pattern2: str) -> bool:
    """Return whether the two glob patterns denote the same language."""

    return not glob_operation_nonempty(
        pattern1,
        pattern2,
        GlobRegion.SYMMETRIC_DIFFERENCE,
    )


def glob_is_empty(pattern: str) -> bool:
    """Return whether one glob pattern denotes the empty language."""

    if not isinstance(pattern, str):
        raise TypeError("pattern must be a str object")

    return not _tokens_nonempty(_compile(pattern))