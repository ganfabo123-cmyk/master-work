/*
 * solver.hpp — Backtracking SLD resolution engine for Epilog.
 * JPL rules: no recursion, bounded stacks, no post-init malloc.
 */

#pragma once

#include <cstdint>
#include "terms.hpp"
#include "variables.hpp"
#include "unifier.hpp"
#include "database.hpp"
#include "atoms.hpp"

constexpr uint32_t GOAL_STACK_CAPACITY   = 512U;
constexpr uint32_t CHOICE_STACK_CAPACITY = 256U;

enum SolveSignal : uint8_t {
    SOLVE_NEXT = 0,
    SOLVE_STOP = 1
};

struct SolverEnv {
    TermArena   *arena        = nullptr;
    TermArena   *clause_arena = nullptr;
    VarRegistry *vars         = nullptr;
    VarRegistry *clause_vars  = nullptr;
    Trail        trail        = {};
    AtomTable   *atoms        = nullptr;
    Database    *db           = nullptr;
};

using SolutionCallback = SolveSignal (*)(SolverEnv *env,
                                         const TermRef *goals_in,
                                         uint32_t goal_count,
                                         void *userdata);

int      solver_env_init(SolverEnv *env,
                          TermArena *arena, TermArena *clause_arena,
                          VarRegistry *vars, VarRegistry *clause_vars,
                          AtomTable *atoms, Database *db);

uint32_t solve(SolverEnv *env, const TermRef *goals, uint32_t goal_count,
               SolutionCallback cb, void *userdata);
