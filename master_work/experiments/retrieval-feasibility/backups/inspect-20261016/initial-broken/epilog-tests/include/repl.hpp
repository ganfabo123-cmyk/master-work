/*
 * repl.hpp — Read-Eval-Print Loop for Epilog.
 * JPL rules: no recursion, bounded buffers, no post-init malloc.
 */

#pragma once

#include "atoms.hpp"
#include "terms.hpp"
#include "variables.hpp"
#include "database.hpp"

constexpr uint32_t REPL_LINE_MAX = 1024U;

struct ReplState {
    AtomTable   atoms;
    Database    db;
    TermArena   clause_arena;
    VarRegistry clause_vars;
    TermArena   query_arena;
    VarRegistry query_vars;
};

int  repl_init(ReplState *s);
int  repl_load_file(ReplState *s, const char *path);
void repl_run(ReplState *s);
