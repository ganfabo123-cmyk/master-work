/*
 * main.cpp — Entry point for the Epilog logic programming runtime.
 *
 * Usage:  epilog [--verbose|-v] [file.pl ...]
 */

#include "include/repl.hpp"
#include "include/log.hpp"
#include <cstdio>
#include <cstring>

int g_verbose = 0;

int main(int argc, char *argv[])
{
    static ReplState s;   /* too large for the stack (~8 MB) */

    LOG_INIT(argc, argv);

    if (repl_init(&s) < 0) {
        fprintf(stderr, "epilog: failed to initialise runtime\n");
        return 1;
    }

    VLOG("%s", "runtime initialised");

    for (int i = 1; i < argc; ++i) {
        if (strncmp(argv[i], "--verbose", 10) == 0) { continue; }
        if (strncmp(argv[i], "-v",         3) == 0) { continue; }
        if (argv[i][0] == '-') { continue; }
        VLOG("loading file: %s", argv[i]);
        if (repl_load_file(&s, argv[i]) < 0) { return 1; }
    }

    repl_run(&s);
    return 0;
}
