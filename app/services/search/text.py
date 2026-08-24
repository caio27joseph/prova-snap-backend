LIKE_ESCAPE_CHAR = "\\"


def escape_like(term: str) -> str:
    """Escape LIKE wildcards so user input is always a literal term: searching
    "100%" must match "100%", not everything starting with "100". This is a
    correctness rule, not SQL-injection defense (bound parameters cover that);
    we deliberately do not expose wildcard search to users (Decisão 7).
    Must be paired with `ilike(..., escape=LIKE_ESCAPE_CHAR)`.
    """
    return (
        term.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )


def like_pattern(term: str) -> str:
    return f"%{escape_like(term)}%"
