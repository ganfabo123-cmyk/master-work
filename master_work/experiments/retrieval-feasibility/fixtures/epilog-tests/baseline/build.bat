@echo off
if not exist build\tests mkdir build\tests
clang++ -std=c++23 -Wall -Wextra -Wpedantic -Iinclude -Itests -g -O0 internals/atoms.cpp tests/test_atoms.cpp "-Wl,/STACK:16777216" -o build/tests/test_atoms.exe
if errorlevel 1 exit /b %errorlevel%
build\tests\test_atoms.exe
