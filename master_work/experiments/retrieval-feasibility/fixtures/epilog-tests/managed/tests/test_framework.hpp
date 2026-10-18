/*
 * test_framework.hpp — Minimal single-header test runner for Epilog.
 *
 * No external dependencies. Compile each test_*.cpp independently and run it.
 * A non-zero exit code means at least one test failed.
 *
 * Usage:
 *   TEST("description") { EXPECT(...); REQUIRE(...); }
 *   int main() { return epilog_test::run_all(); }
 *
 * Macros:
 *   EXPECT(expr)        — record failure if expr is false; continue test
 *   EXPECT_EQ(a, b)     — record failure if a != b; print both values
 *   EXPECT_NE(a, b)     — record failure if a == b
 *   EXPECT_NULL(p)      — record failure if p != nullptr
 *   EXPECT_NOTNULL(p)   — record failure if p == nullptr
 *   REQUIRE(expr)       — abort current test immediately if expr is false
 *   TEST(name)          — declare a test case (registers automatically)
 */

#pragma once

#include <cstdio>
#include <cstring>
#include <functional>
#include <vector>
#include <string>

namespace epilog_test {

struct Result {
    bool        passed;
    std::string name;
    std::string failure_msg;
};

struct Registry {
    struct Entry { std::string name; std::function<void()> fn; };
    std::vector<Entry>  entries;
    std::vector<Result> results;
    int                 failures = 0;

    static Registry &get() { static Registry r; return r; }

    void add(std::string name, std::function<void()> fn) {
        entries.push_back({ std::move(name), std::move(fn) });
    }
};

/* Thrown to abort a single test on REQUIRE failure. */
struct TestAbort { std::string msg; };

/* Per-test state (reset for each test). */
inline thread_local int  tl_failures    = 0;
inline thread_local bool tl_in_test     = false;

/* Record a failure inside a running test. */
inline void record_failure(const char *file, int line, const char *expr)
{
    tl_failures++;
    fprintf(stderr, "    FAIL  %s:%d  %s\n", file, line, expr);
}

inline int run_all()
{
    Registry &reg = Registry::get();
    int total   = 0;
    int passed  = 0;

    for (auto &entry : reg.entries) {
        total++;
        tl_failures = 0;
        tl_in_test  = true;
        bool aborted = false;
        std::string abort_msg;

        try {
            entry.fn();
        } catch (const TestAbort &a) {
            aborted   = true;
            abort_msg = a.msg;
            tl_failures++;
        }

        tl_in_test = false;
        bool ok = (tl_failures == 0);
        if (ok) {
            passed++;
            printf("  PASS  %s\n", entry.name.c_str());
        } else {
            printf("  FAIL  %s", entry.name.c_str());
            if (aborted) { printf("  [aborted: %s]", abort_msg.c_str()); }
            printf("\n");
        }
    }

    printf("\n%d/%d tests passed", passed, total);
    if (total - passed > 0) {
        printf("  (%d FAILED)", total - passed);
    }
    printf("\n");
    return (passed == total) ? 0 : 1;
}

/* Registration helper — instantiated by the TEST macro. */
struct Registrar {
    Registrar(const char *name, std::function<void()> fn) {
        Registry::get().add(name, std::move(fn));
    }
};

} // namespace epilog_test

/* ---- Public macros ------------------------------------------------------- */

#define EPILOG_TEST_CONCAT2(a, b) a##b
#define EPILOG_TEST_CONCAT(a, b) EPILOG_TEST_CONCAT2(a, b)

#define EPILOG_TEST_IMPL(name, uid) \
    static void EPILOG_TEST_CONCAT(_test_body_, uid)(); \
    static ::epilog_test::Registrar EPILOG_TEST_CONCAT(_reg_, uid)(name, EPILOG_TEST_CONCAT(_test_body_, uid)); \
    static void EPILOG_TEST_CONCAT(_test_body_, uid)()

#define TEST(name) EPILOG_TEST_IMPL(name, __COUNTER__)

#define EXPECT(expr) \
    do { \
        if (!(expr)) { \
            ::epilog_test::record_failure(__FILE__, __LINE__, #expr); \
        } \
    } while (0)

#define EXPECT_EQ(a, b) \
    do { \
        auto _a = (a); auto _b = (b); \
        if (!(_a == _b)) { \
            char _buf[256]; \
            snprintf(_buf, sizeof(_buf), "%s == %s", #a, #b); \
            ::epilog_test::record_failure(__FILE__, __LINE__, _buf); \
        } \
    } while (0)

#define EXPECT_NE(a, b) \
    do { \
        auto _a = (a); auto _b = (b); \
        if (_a == _b) { \
            char _buf[256]; \
            snprintf(_buf, sizeof(_buf), "%s != %s", #a, #b); \
            ::epilog_test::record_failure(__FILE__, __LINE__, _buf); \
        } \
    } while (0)

#define EXPECT_NULL(p) \
    do { \
        if ((p) != nullptr) { \
            ::epilog_test::record_failure(__FILE__, __LINE__, #p " == nullptr"); \
        } \
    } while (0)

#define EXPECT_NOTNULL(p) \
    do { \
        if ((p) == nullptr) { \
            ::epilog_test::record_failure(__FILE__, __LINE__, #p " != nullptr"); \
        } \
    } while (0)

#define REQUIRE(expr) \
    do { \
        if (!(expr)) { \
            char _buf[256]; \
            snprintf(_buf, sizeof(_buf), "REQUIRE failed: %s", #expr); \
            throw ::epilog_test::TestAbort{ _buf }; \
        } \
    } while (0)
