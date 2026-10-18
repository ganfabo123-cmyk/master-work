"""Recover the original solver-test failure; preparation only."""
from restore_replacements import snapshot, save

TRACE = 'c99032e9-377b-4ae9-a9a9-ec7752b059cd'
files, provenance, _, _ = snapshot(TRACE, 'd:/Epilog/', 1126, {'.cpp', '.hpp'})
files['build.bat'] = (
    '@echo off\n'
    'if not exist build\\tests mkdir build\\tests\n'
    'clang++ -std=c++23 -Iinclude -Itests -g -O0 '
    'internals/atoms.cpp internals/variables.cpp internals/terms.cpp '
    'parser/lexer.cpp parser/parser.cpp engine/database.cpp engine/unifier.cpp '
    'engine/builtins.cpp engine/solver.cpp repl.cpp tests/test_solver.cpp '
    '-o build/tests/test_solver.exe\n'
    'if errorlevel 1 exit /b %errorlevel%\n'
    'build\\tests\\test_solver.exe\n'
)
files['README.md'] = '# Epilog solver tests\n\n`./build.bat` compiles and runs the solver tests.\n'
save('epilog-solver', files, provenance, TRACE, 1128)
print('Recovered original solver-test snapshot for both arms')
