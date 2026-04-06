from __future__ import annotations


def split_lines(text: str) -> list[str]:
    return [line.rstrip('\n') for line in (text or '').splitlines()]


def trim_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and lines[start].strip() == '':
        start += 1
    while end > start and lines[end - 1].strip() == '':
        end -= 1
    return lines[start:end]


def previous_done_index(done_indexes: list[int], *, target_index: int) -> int:
    for index in reversed(done_indexes):
        if index < target_index:
            return index
    return -1


__all__ = ['previous_done_index', 'split_lines', 'trim_blank_edges']
