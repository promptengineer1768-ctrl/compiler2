"""Source catalog for Phase 11 stock BASIC language fixture capture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast


@dataclass(frozen=True)
class SourceCase:
    """One stock BASIC observation source."""

    reference_mode: str
    source_lines: tuple[str, ...]
    interactive_input: tuple[str, ...] = ()


_BASICV2_FUNCTIONS: Final = {
    "ABS": "PRINT ABS(-2)",
    "ASC": 'PRINT ASC("A")',
    "ATN": "PRINT ATN(1)",
    "CHR$": "PRINT CHR$(65)",
    "COS": "PRINT COS(0)",
    "EXP": "PRINT EXP(0)",
    "FRE": 'PRINT FRE("")',
    "INT": "PRINT INT(-1.2)",
    "LEFT$": 'PRINT LEFT$("ABC",2)',
    "LEN": 'PRINT LEN("ABC")',
    "LOG": "PRINT LOG(1)",
    "MID$": 'PRINT MID$("ABCD",2,2)',
    "PEEK": "PRINT PEEK(53280)",
    "POS": "PRINT POS(0)",
    "RIGHT$": 'PRINT RIGHT$("ABC",2)',
    "RND": "PRINT RND(1)",
    "SGN": "PRINT SGN(-2)",
    "SIN": "PRINT SIN(0)",
    "SPC": 'PRINT "A";SPC(2);"B"',
    "SQR": "PRINT SQR(4)",
    "ST": "PRINT ST",
    "STR$": "PRINT STR$(12)",
    "TAB": 'PRINT TAB(5);"X"',
    "TAN": "PRINT TAN(0)",
    "TI$": "PRINT LEN(TI$)",
    "USR": "PRINT USR(0)",
    "VAL": 'PRINT VAL("123")',
}

_BASICV2_STATEMENTS: Final = {
    "CLOSE": ("10 CLOSE 1",),
    "CLR": ("CLR",),
    "CMD": ("10 OPEN1,3:CMD1:PRINT:PRINT#1:CLOSE1",),
    "CONT": ("CONT",),
    "DATA": ("10 DATA 7", "20 READ A:PRINT A"),
    "DEF": ("10 DEF FN A(X)=X+1", "20 PRINT FN A(2)"),
    "DIM": ("10 DIM A(2)", "20 A(1)=5:PRINT A(1)"),
    "END": ('10 PRINT "A"', "20 END", '30 PRINT "B"'),
    "FN": ("10 DEF FN A(X)=X+1", "20 PRINT FN A(2)"),
    "FOR": ("10 FOR I=1 TO 3:PRINT I:NEXT",),
    "GET": ("10 GET A$:PRINT LEN(A$)",),
    "GOSUB": ("10 GOSUB 30", '20 PRINT "DONE":END', '30 PRINT "SUB":RETURN'),
    "GOTO": ("10 GOTO 30", '20 PRINT "BAD"', '30 PRINT "OK"'),
    "IF": ('10 IF 1 THEN PRINT "YES"',),
    "INPUT": SourceCase("program", ('10 INPUT "A";A', "20 PRINT A"), ("7",)),
    "INPUT#": ("10 OPEN1,3", "20 INPUT#1,A$", "30 CLOSE1"),
    "LET": ("10 LET A=7", "20 PRINT A"),
    "LIST": ("10 PRINT 1", "LIST"),
    "LOAD": ('LOAD "NO SUCH FILE",8',),
    "NEW": ("10 PRINT 1", "NEW", "LIST"),
    "NEXT": ("10 FOR I=1 TO 2:PRINT I:NEXT",),
    "ON": ("10 ON 2 GOTO 40,50", '40 PRINT "BAD":END', '50 PRINT "OK"'),
    "OPEN": ("10 OPEN1,3:CLOSE1",),
    "POKE": ("POKE 53280,PEEK(53280)",),
    "PRINT": ('PRINT "OK"',),
    "PRINT#": ('10 OPEN1,3:PRINT#1,"OK":CLOSE1',),
    "READ": ("10 DATA 9", "20 READ A:PRINT A"),
    "REM": ("10 REM IGNORED", '20 PRINT "OK"'),
    "RESTORE": ("10 DATA 1", "20 READ A:RESTORE:READ B:PRINT A;B"),
    "RETURN": ("10 RETURN",),
    "RUN": ('10 PRINT "OK"', "RUN"),
    "SAVE": ('SAVE "PHASE11",8',),
    "STOP": ('10 PRINT "A"', "20 STOP", '30 PRINT "B"'),
    "SYS": ("SYS 65523",),
    "VERIFY": ('VERIFY "NO SUCH FILE",8',),
    "WAIT": ("10 WAIT 53265,128", '20 PRINT "OK"'),
}

_BASICV35_FORMS: Final = {
    "BASIC2": ("BASIC 2",),
    "BASIC3.5": ('PRINT "3.5"',),
    "DATA": ("10 DATA 7", "20 READ A:PRINT A"),
    "DIM": ("10 DIM A(2)", "20 A(1)=5:PRINT A(1)"),
    "DO": ("10 DO:PRINT 1:EXIT:LOOP",),
    "DO UNTIL": ("10 I=0:DO UNTIL I=2:I=I+1:PRINT I:LOOP",),
    "DO WHILE": ("10 I=0:DO WHILE I<2:I=I+1:PRINT I:LOOP",),
    "ELSE": ('10 IF 0 THEN PRINT "BAD":ELSE PRINT "OK"',),
    "END": ('10 PRINT "A"', "20 END", '30 PRINT "B"'),
    "EXIT": ("10 DO:PRINT 1:EXIT:LOOP",),
    "EXIT DO": ('10 DO:PRINT "OK":EXIT:LOOP',),
    "FOR": ("10 FOR I=1 TO 3:PRINT I:NEXT",),
    "GOSUB": ("10 GOSUB 30", '20 PRINT "DONE":END', '30 PRINT "SUB":RETURN'),
    "GOTO": ("10 GOTO 30", '20 PRINT "BAD"', '30 PRINT "OK"'),
    "IF": ('10 IF 1 THEN PRINT "YES"',),
    "INPUT": SourceCase("program", ('10 INPUT "A";A', "20 PRINT A"), ("7",)),
    "LET": ("10 LET A=7", "20 PRINT A"),
    "LOOP": ("10 I=0:DO:I=I+1:PRINT I:LOOP WHILE I<3",),
    "LOOP UNTIL": ("10 I=0:DO:I=I+1:PRINT I:LOOP UNTIL I=2",),
    "LOOP WHILE": ("10 I=0:DO:I=I+1:PRINT I:LOOP WHILE I<2",),
    "NEXT": ("10 FOR I=1 TO 2:PRINT I:NEXT",),
    "ON": ("10 ON 2 GOTO 40,50", '40 PRINT "BAD":END', '50 PRINT "OK"'),
    "POKE": ("POKE 53280,PEEK(53280)",),
    "PRINT": ('PRINT "OK"',),
    "READ": ("10 DATA 9", "20 READ A:PRINT A"),
    "REM": ("10 REM IGNORED", '20 PRINT "OK"'),
    "RESTORE": ("10 DATA 1", "20 READ A:RESTORE:READ B:PRINT A;B"),
    "RETURN": ("10 RETURN",),
    "STOP": ('10 PRINT "A"', "20 STOP", '30 PRINT "B"'),
    "SYS": ("SYS 65523",),
    "UNTIL": ("10 I=0:DO:I=I+1:PRINT I:LOOP UNTIL I=2",),
    "WAIT": ("10 WAIT 53265,128", '20 PRINT "OK"'),
    "WHILE": ("10 I=0:DO WHILE I<2:I=I+1:PRINT I:LOOP",),
}


def stock_source_case(profile: str, keyword: str, mode: str) -> SourceCase | None:
    """Return source for one stock BASIC E2E scenario."""
    reference_mode = "program" if mode == "compile" else mode
    if profile == "basicv2":
        if keyword in _BASICV2_FUNCTIONS:
            line = _BASICV2_FUNCTIONS[keyword]
            lines = (line,) if reference_mode == "immediate" else (f"10 {line}",)
            return SourceCase(reference_mode, lines)
        value = _BASICV2_STATEMENTS.get(keyword)
        if isinstance(value, SourceCase):
            return value
        if value is not None:
            return SourceCase(reference_mode, cast(tuple[str, ...], value))
    if profile == "basicv35":
        value = _BASICV35_FORMS.get(keyword)
        if isinstance(value, SourceCase):
            return value
        if value is not None:
            return SourceCase(reference_mode, cast(tuple[str, ...], value))
    return None
