/*
 * log.hpp — Verbose logging for the Epilog runtime.
 *
 * Pass --verbose or -v on the command line to activate.
 * JPL rules: no heap, no recursion.
 */

#pragma once

#include <cstdio>
#include <cstring>
#include <cstdarg>

extern int g_verbose;

inline void log_init(int argc, char *argv[])
{
    g_verbose = 0;
    for (int i = 1; i < argc; ++i) {
        if (strncmp(argv[i], "--verbose", 10) == 0 ||
            strncmp(argv[i], "-v",         3) == 0) {
            g_verbose = 1;
        }
    }
}

inline void vlog(const char *subsys, const char *fmt, ...)
{
    if (!g_verbose) { return; }
    va_list ap;
    fprintf(stderr, "[%s] ", subsys);
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
}

#define LOG_INIT(argc, argv)          log_init((argc), (argv))
#define VLOG(fmt, ...)                vlog("epilog", (fmt), __VA_ARGS__)
#define VLOG_SUBSYS(s, fmt, ...)      vlog((s),      (fmt), __VA_ARGS__)
