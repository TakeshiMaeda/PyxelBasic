# -*- coding: utf-8 -*-
"""Error codes and messages for PyxelBasic (single source of truth).

Code raises ``BasicError(Err.SOMETHING, *params)``; the human-readable message
is looked up in MESSAGES and formatted with the params here, so the message text
lives in exactly one place. Codes are grouped by hundreds:

    1xx  syntax / parse
    2xx  type
    3xx  runtime / control flow
    4xx  array / data
    5xx  file / command
"""

from enum import IntEnum


class Err(IntEnum):
    # --- 1xx: syntax / parse ---
    SYNTAX_ERROR = 101
    UNSUPPORTED_STATEMENT = 102
    INVALID_EXPRESSION = 103
    EXPECTED_LPAREN = 104
    EXPECTED_RPAREN = 105
    EXPECTED_EQUALS = 106
    ASSIGN_TARGET_NOT_VAR = 107
    EXPECTED_THEN = 108
    NOTHING_AFTER_THEN = 109
    MISSING_FOR_VAR = 110
    EXPECTED_EQUALS_IN_FOR = 111
    EXPECTED_TO_IN_FOR = 112
    INVALID_DIM_SYNTAX = 113
    INVALID_LOCATE_SYNTAX = 114
    INVALID_LINE_SYNTAX = 115
    VSYNC_KEYWORD_REQUIRED = 116
    VSYNC_ON_OFF_REQUIRED = 117
    UNTERMINATED_STRING = 118
    INVALID_CHAR = 119
    INVALID_COMPARISON_OP = 120

    # --- 2xx: type ---
    NUMBER_REQUIRED = 201
    TYPE_MISMATCH = 202
    STRING_TO_NUMERIC = 203

    # --- 3xx: runtime / control flow ---
    DIVISION_BY_ZERO = 301
    LINE_NOT_FOUND = 302
    RETURN_WITHOUT_GOSUB = 303
    NEXT_WITHOUT_FOR = 304
    NEXT_VAR_WITHOUT_FOR = 305

    # --- 4xx: array / data ---
    SUBSCRIPT_OUT_OF_RANGE = 401
    OUT_OF_DATA = 402

    # --- 5xx: file / command ---
    SAVE_REQUIRES_NAME = 501
    LOAD_REQUIRES_NAME = 502


MESSAGES = {
    # 1xx: syntax / parse
    Err.SYNTAX_ERROR: "Syntax error",
    Err.UNSUPPORTED_STATEMENT: "Unsupported statement: %s",
    Err.INVALID_EXPRESSION: "Invalid expression",
    Err.EXPECTED_LPAREN: "Expected '('",
    Err.EXPECTED_RPAREN: "Expected ')'",
    Err.EXPECTED_EQUALS: "Expected '='",
    Err.ASSIGN_TARGET_NOT_VAR: "Assignment target is not a variable",
    Err.EXPECTED_THEN: "Expected THEN",
    Err.NOTHING_AFTER_THEN: "Nothing after THEN",
    Err.MISSING_FOR_VAR: "Missing FOR variable",
    Err.EXPECTED_EQUALS_IN_FOR: "Expected '=' in FOR",
    Err.EXPECTED_TO_IN_FOR: "Expected TO in FOR",
    Err.INVALID_DIM_SYNTAX: "Invalid DIM syntax",
    Err.INVALID_LOCATE_SYNTAX: "Invalid LOCATE syntax",
    Err.INVALID_LINE_SYNTAX: "Invalid LINE syntax ('-' required)",
    Err.VSYNC_KEYWORD_REQUIRED: "VSYNC: keyword required",
    Err.VSYNC_ON_OFF_REQUIRED: "VSYNC: ON or OFF required",
    Err.UNTERMINATED_STRING: "Unterminated string",
    Err.INVALID_CHAR: "Invalid character: '%s'",
    Err.INVALID_COMPARISON_OP: "Invalid comparison operator",

    # 2xx: type
    Err.NUMBER_REQUIRED: "Number required",
    Err.TYPE_MISMATCH: "Type mismatch in comparison",
    Err.STRING_TO_NUMERIC: "Cannot assign string to numeric variable: %s",

    # 3xx: runtime / control flow
    Err.DIVISION_BY_ZERO: "Division by zero",
    Err.LINE_NOT_FOUND: "Line %d not found",
    Err.RETURN_WITHOUT_GOSUB: "RETURN without GOSUB",
    Err.NEXT_WITHOUT_FOR: "NEXT without FOR",
    Err.NEXT_VAR_WITHOUT_FOR: "NEXT %s without FOR",

    # 4xx: array / data
    Err.SUBSCRIPT_OUT_OF_RANGE: "Subscript out of range: %s",
    Err.OUT_OF_DATA: "Out of DATA",

    # 5xx: file / command
    Err.SAVE_REQUIRES_NAME: "SAVE requires a file name",
    Err.LOAD_REQUIRES_NAME: "LOAD requires a file name",
}


class BasicError(Exception):
    """A runtime / syntax error identified by an Err code.

    Raise as ``BasicError(Err.CODE, *params)``. The message is looked up in
    MESSAGES and formatted with params; ``str(err)`` yields the formatted
    message, while ``err.code`` / ``err.params`` expose the structured info.
    """

    def __init__(self, code, *params):
        self.code = code
        self.params = params
        if code in MESSAGES:
            template = MESSAGES[code]
            message = template % params if params else template
        else:
            message = "Unknown error (%r)" % (code,)
        super().__init__(message)


# Consistency check: every declared code must have a message and vice versa, so
# a new code without a message (or a stray message) fails fast at import.
assert set(Err) == set(MESSAGES), \
    "Err / MESSAGES mismatch: %s" % (set(Err) ^ set(MESSAGES))
