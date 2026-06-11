# Example Prompts

Use these from the CLI, TUI, or browser dashboard.

## Build

```text
Build a Python todo app on my desktop titled todo with add, list, complete, and delete commands.
```

```text
Build a small Flask app titled habit tracker with routes for creating habits, checking them off, and viewing a weekly summary.
```

```text
Create a command-line markdown link checker titled link check that scans a folder and reports broken local links.
```

## Debug

```text
/fix This function raises IndexError when the list is empty. Explain the root cause and return corrected code.
```

```text
/review Review this file for bugs, edge cases, and missing tests. Prioritize concrete issues.
```

## Explain

```text
/explain Explain this stack trace and suggest the smallest safe fix.
```

```text
/explain Walk me through this module as if I am new to the codebase.
```

## Tests

```text
/test Write pytest tests for this function, including edge cases and failure modes.
```

```text
/test Add tests for the config loader so missing files, defaults, and explicit backends are covered.
```

## Refactor

```text
/refactor Simplify this class without changing behavior. Keep public method names stable.
```

```text
/refactor Split this long function into small helpers and explain the new structure briefly.
```
