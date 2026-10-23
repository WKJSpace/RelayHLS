#include "constants.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <omp.h>
#include <vector>

static int clip(int x, int lo, int hi) { return std::min(hi, std::max(lo, x)); }
static int floor_div(int x, int d) { return x >= 0 ? x/d : -((-x+d-1)/d); }
static constexpr int post_min = -(1 << POST_MAG_BITS);
static constexpr int post_max = (1 << POST_MAG_BITS)-1;

struct Workspace {
    std::vector<int> q, r, posterior;
    std::vector<uint8_t> hard, best;
    Workspace() : q(NUM_EDGES), r(NUM_EDGES), posterior(NUM_FAULTS),
                  hard(NUM_FAULTS), best(NUM_FAULTS) {}
};

static bool decode(const std::vector<int>& priors, const std::vector<uint8_t>& syndrome,
                   Workspace& work, int threads, int& updates, int& solutions) {
    int* __restrict__ q = work.q.data();
    int* __restrict__ r = work.r.data();
    int* __restrict__ posterior = work.posterior.data();
    uint8_t* __restrict__ hard = work.hard.data();
    const int* __restrict__ prior = priors.data();
    std::fill(work.r.begin(), work.r.end(), 0);
    std::fill(work.hard.begin(), work.hard.end(), 0);
    std::fill(work.best.begin(), work.best.end(), 0);
    std::copy(priors.begin(), priors.end(), work.posterior.begin());
    for (int c = 0; c < NUM_DETECTORS; ++c)
        for (int k = 0; k < H_ROW_DEGREES[c]; ++k)
            q[EDGE_FOR_CHECK_POS[c][k]] = prior[H_ROW_NEIGHBORS[c][k]];
    updates = solutions = 0;
    int64_t best_cost = WEIGHT_MAX;
    for (int leg = 0; leg < MAX_LEGS && updates < GLOBAL_MAX_ITERS; ++leg) {
        int leg_updates = std::min(MAX_ITERS_PER_LEG, GLOBAL_MAX_ITERS-updates);
        int beta = LEG_BETA[leg];
        bool converged = false;
        for (int local = 0; local < leg_updates; ++local) {
            int shift = std::min(local, ALPHA_SHIFT_MAX);
            bool first = updates == 0;
            #pragma omp parallel for num_threads(threads) if(threads > 1) schedule(static)
            for (int c = 0; c < NUM_DETECTORS; ++c) {
                int minimum = MSG_MAX_MAG, second = MSG_MAX_MAG;
                int parity = syndrome[c], ties = 0, degree = H_ROW_DEGREES[c];
                #ifdef RELAY_CPU_SIMD
                #pragma omp simd reduction(min:minimum) reduction(^:parity)
                #endif
                for (int k = 0; k < degree; ++k) {
                    int value = q[EDGE_FOR_CHECK_POS[c][k]];
                    minimum = std::min(minimum, std::abs(value));
                    parity ^= value < 0;
                }
                #ifdef RELAY_CPU_SIMD
                #pragma omp simd reduction(min:second) reduction(+:ties)
                #endif
                for (int k = 0; k < degree; ++k) {
                    int magnitude = std::abs(q[EDGE_FOR_CHECK_POS[c][k]]);
                    ties += magnitude == minimum;
                    second = std::min(second, magnitude > minimum ? magnitude : MSG_MAX_MAG);
                }
                if (ties > 1) second = minimum;
                int raw_minimum = minimum;
                if (shift) {
                    minimum -= minimum >> shift;
                    second -= second >> shift;
                }
                for (int k = 0; k < degree; ++k) {
                    int e = EDGE_FOR_CHECK_POS[c][k], value = q[e];
                    int magnitude = ties == 1 && std::abs(value) == raw_minimum ? second : minimum;
                    r[e] = (parity ^ (value < 0)) ? -magnitude : magnitude;
                }
            }
            #pragma omp parallel for num_threads(threads) if(threads > 1) schedule(static)
            for (int v = 0; v < NUM_FAULTS; ++v) {
                int degree = H_COL_DEGREES[v];
                if (!degree) continue;
                int bias = first ? prior[v]
                                 : clip(floor_div(beta*prior[v], MEM_SCALE)
                                        + floor_div((MEM_SCALE-beta)*posterior[v], MEM_SCALE),
                                        post_min, post_max);
                int incoming = 0;
                #ifdef RELAY_CPU_SIMD
                #pragma omp simd reduction(+:incoming)
                #endif
                for (int k = 0; k < degree; ++k) incoming += r[EDGE_FOR_VAR_POS[v][k]];
                int updated = clip(bias+incoming, post_min, post_max);
                posterior[v] = updated;
                hard[v] = updated < 0;
                for (int k = 0; k < degree; ++k) {
                    int e = EDGE_FOR_VAR_POS[v][k];
                    int extrinsic = clip(updated-r[e], post_min, post_max);
                    q[e] = clip(extrinsic, -MSG_MAX_MAG, MSG_MAX_MAG);
                }
            }
            ++updates;
            if ((local+1)%CONVERGENCE_CHECK_INTERVAL == 0 || local+1 == leg_updates) {
                int mismatch = 0;
                #pragma omp parallel for num_threads(threads) if(threads > 1) schedule(static) reduction(|:mismatch)
                for (int c = 0; c < NUM_DETECTORS; ++c) {
                    int parity = 0, degree = H_ROW_DEGREES[c];
                    #ifdef RELAY_CPU_SIMD
                    #pragma omp simd reduction(^:parity)
                    #endif
                    for (int k = 0; k < degree; ++k) parity ^= hard[H_ROW_NEIGHBORS[c][k]];
                    mismatch |= parity != syndrome[c];
                }
                if (!mismatch) { converged = true; break; }
            }
        }
        if (converged) {
            ++solutions;
            int64_t cost = 0;
            #ifdef RELAY_CPU_SIMD
            #pragma omp simd reduction(+:cost)
            #endif
            for (int v = 0; v < NUM_FAULTS; ++v)
                if (H_COL_DEGREES[v] && hard[v]) cost += prior[v];
            if (cost < best_cost) {
                best_cost = cost;
                std::copy(work.hard.begin(), work.hard.end(), work.best.begin());
            }
            if (solutions >= MAX_SOLUTIONS) break;
        }
    }
    return solutions > 0;
}

int main(int argc, char** argv) {
    int threads = argc > 1 ? std::stoi(argv[1]) : 1;
    if (threads < 1 || threads > 16) return 1;
    omp_set_dynamic(0);
    int shots;
    if (!(std::cin >> shots) || shots < 1) return 2;
    std::vector<int> priors(NUM_FAULTS);
    for (int& value : priors)
        if (!(std::cin >> value) || value < 0 || value > MSG_MAX_MAG) return 3;
    Workspace work;
    std::vector<uint8_t> syndrome(NUM_DETECTORS);
    for (int shot = 0; shot < shots; ++shot) {
        for (uint8_t& bit : syndrome) {
            int value;
            if (!(std::cin >> value) || (value != 0 && value != 1)) return 4;
            bit = value;
        }
        int updates, solutions;
        auto start = std::chrono::steady_clock::now();
        bool converged = decode(priors, syndrome, work, threads, updates, solutions);
        auto end = std::chrono::steady_clock::now();
        double microseconds = std::chrono::duration<double, std::micro>(end-start).count();
        std::cout << updates << ' ' << solutions << ' ' << converged << ' ';
        for (uint8_t bit : work.best) std::cout << (int)bit;
        std::cout << ' ' << std::setprecision(10) << microseconds << '\n';
    }
    return 0;
}
