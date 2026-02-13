# Task: Hello AutoFlow

## Context
- Repo: python/shell
- Key files: hello.py, test_hello.py
- Background: AutoFlow E2E system test task

## Objective
- Goal: Create hello.py and test_hello.py for AutoFlow E2E verification
- Non-goals: No packaging, no CI config, no complex project structure

## Constraints
- Files in project root
- Minimal implementation

## Steps
- [x] S1: Create hello.py with main() that prints Hello, AutoFlow!
- [>] S2: Create test_hello.py with pytest test using capsys

## Done
- python3 hello.py prints Hello, AutoFlow!
- python3 -m pytest test_hello.py passes
