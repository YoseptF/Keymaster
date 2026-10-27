#pragma once

#include <cstdio>
#include <cstdlib>
#include <string>

static int gFailures = 0;

#define CHECK(cond)                                                                  \
    do {                                                                             \
        if (!(cond)) {                                                               \
            std::fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond); \
            ++gFailures;                                                             \
        }                                                                            \
    } while (0)

#define CHECK_EQ(a, b)                                                               \
    do {                                                                             \
        auto va = (a);                                                               \
        auto vb = (b);                                                               \
        if (!(va == vb)) {                                                           \
            std::fprintf(stderr, "%s:%d: CHECK_EQ failed: %s != %s\n", __FILE__, __LINE__, #a, #b); \
            ++gFailures;                                                             \
        }                                                                            \
    } while (0)

static int finish(const char* name) {
    if (gFailures) {
        std::fprintf(stderr, "%s: %d failure(s)\n", name, gFailures);
        return 1;
    }
    std::printf("%s: ok\n", name);
    return 0;
}
