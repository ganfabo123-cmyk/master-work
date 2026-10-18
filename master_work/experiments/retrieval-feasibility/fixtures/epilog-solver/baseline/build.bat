@echo off
if not exist build\tests mkdir build\tests
clang++ -std=c++23 -Iinclude -Itests -g -O0 internals/atoms.cpp internals/variables.cpp internals/terms.cpp parser/lexer.cpp parser/parser.cpp engine/database.cpp engine/unifier.cpp engine/builtins.cpp engine/solver.cpp repl.cpp tests/test_solver.cpp -o build/tests/test_solver.exe
if errorlevel 1 exit /b %errorlevel%
build\tests\test_solver.exe
