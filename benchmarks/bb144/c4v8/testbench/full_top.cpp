#include "decoder_top.h"
#include "relay_bp.h"
#include <iostream>
#include <fstream>

#ifndef RELAYHLS_INPUT_PATH
#define RELAYHLS_INPUT_PATH "inputs.txt"
#endif

// Full-memory interface fixture: zero carry input, commit all mapped faults.
// Compare the full top with its complete controller, then emit frame/carry for
// comparison with independent canonical H/A parity in the Python runner.
int main() {
    std::ifstream physical_inputs(RELAYHLS_INPUT_PATH);
    if (!physical_inputs) return 8;
    std::cin.rdbuf(physical_inputs.rdbuf());
    int shots;
    if (!(std::cin >> shots) || shots < 1) return 1;
    static Prior priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH];
    static PackedPriors packed_priors[NUM_PRIOR_WORDS];
    for (int j = 0; j < NUM_FAULTS; ++j) {
        int value;
        if (!(std::cin >> value) || value < 0 || value > MSG_MAX_MAG) return 2;
        priors[j % PRIOR_BANK_FACTOR][j / PRIOR_BANK_FACTOR] = value;
        int lane = j % PRIOR_PACK_FACTOR;
        packed_priors[j / PRIOR_PACK_FACTOR].range((lane + 1) * MSG_INT_BITS - 1,
                                                   lane * MSG_INT_BITS) = value;
    }
    for (int shot = 0; shot < shots; ++shot) {
        PackedBits syndrome[NUM_DETECTOR_WORDS] = {}, best[NUM_FAULT_WORDS] = {};
        PackedBits top_best[NUM_FAULT_WORDS] = {}, carry_in[CARRY_WORDS] = {}, carry_out[CARRY_WORDS] = {};
        // Explicit assignment is required for local vendor arbitrary-precision
        // arrays; aggregate braces did not provide zero carry in this build.
        for (int w = 0; w < NUM_DETECTOR_WORDS; ++w) syndrome[w] = 0;
        for (int w = 0; w < NUM_FAULT_WORDS; ++w) best[w] = top_best[w] = 0;
        for (int w = 0; w < CARRY_WORDS; ++w) carry_in[w] = carry_out[w] = 0;
        for (int i = 0; i < NUM_DETECTORS; ++i) {
            int bit;
            if (!(std::cin >> bit) || (bit != 0 && bit != 1)) return 3;
            set_packed_bit(syndrome, i, bit);
        }
        for (int w = 0; w < CARRY_WORDS; ++w) {
            if (carry_in[w] != 0) {
                std::cerr << "shot=" << shot << " uninitialized test carry[" << w
                          << "]=" << carry_in[w] << '\n';
                return 6;
            }
        }
        int iterations = 0, candidates = 0, top_iterations = 0;
        bool converged = relay_bp_decode(syndrome, priors, best, iterations, candidates);
        bool top_converged = false;
        PauliFrame frame = 0;
        relaybp_top(syndrome, carry_in, packed_priors, top_best, &frame, carry_out,
                    &top_iterations, &top_converged);
        if (iterations != top_iterations || converged != top_converged) {
            std::cerr << "shot=" << shot << " controller_updates=" << iterations
                      << " top_updates=" << top_iterations
                      << " controller_converged=" << converged
                      << " top_converged=" << top_converged << '\n';
            return 4;
        }
        for (int w = 0; w < NUM_FAULT_WORDS; ++w)
            if (best[w] != top_best[w]) return 5;
        std::cout << iterations << ' ' << candidates << ' ' << converged << ' ';
        for (int j = 0; j < NUM_FAULTS; ++j) std::cout << (int)get_packed_bit(best, j);
        std::cout << ' ';
        for (int k = 0; k < K_OBSERVABLES; ++k) std::cout << (int)frame[k];
        std::cout << ' ';
        for (int i = 0; i < M_PER_CYCLE; ++i) std::cout << (int)get_packed_bit(carry_out, i);
        std::cout << '\n';
    }
    return 0;
}
