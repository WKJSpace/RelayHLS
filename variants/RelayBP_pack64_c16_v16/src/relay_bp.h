#ifndef RELAY_BP_H
#define RELAY_BP_H

#include "types.h"
#include "constants.h"
#include "packed_bits.h"
#include "bp_iteration.h"

inline void clear_fault_bits(PackedBits words[NUM_FAULT_WORDS]) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    CLEAR_FAULT_WORDS:
    for (int w = 0; w < NUM_FAULT_WORDS; w++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        words[w] = 0;
    }
}

inline Prior read_prior_banked(
    const Prior priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    int         j
) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    return priors[j % PRIOR_BANK_FACTOR][j / PRIOR_BANK_FACTOR];
}

// Picking the best solution.
inline WEIGHT compute_weight(
    const PackedBits hard_decisions[NUM_FAULT_WORDS],
    const Prior      priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    WEIGHT w = 0;

    WEIGHT_ACTIVE_FAULTS:
    for (int active = 0; active < NUM_ACTIVE_FAULTS; active++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        int j = ACTIVE_FAULT_INDEX[active];
        if (get_packed_bit(hard_decisions, j)) {
            w += (WEIGHT)read_prior_banked(priors, j);
        }
    }
    return w;
}

// Initialize the messages and marginals to priors.
inline void init_messages(
    PackedMessage v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    PackedMessage c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    Posterior   marginals[NUM_FAULTS],
    const Prior priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH]
) {
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_LANE  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_LANE  dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_ADDR  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_ADDR  dim=3 type=complete
    // clang-format on

    INIT_V_TO_C_GROUPS:
    for (int j_base = 0; j_base < NUM_FAULTS; j_base += VNU_PARALLEL) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        int group = j_base / VNU_PARALLEL;
        Prior lane_priors[VNU_PARALLEL];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=lane_priors dim=1 type=complete
        // clang-format on

        INIT_V_TO_C_PRIOR_LANES:
        for (int lane = 0; lane < VNU_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int j = j_base + lane;
            lane_priors[lane] = (j < NUM_FAULTS) ? read_prior_banked(priors, j) : (Prior)0;
        }

        INIT_V_TO_C_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            INIT_V_TO_C_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (VNU_EDGE_VALID[group][bank][port]) {
                    int lane = VNU_EDGE_LANE[group][bank][port];
                    int addr = VNU_EDGE_ADDR[group][bank][port];
                    Message init_msg;
                    init_msg.sign = 0;
                    init_msg.mag  = lane_priors[lane];
                    v_to_c[bank][addr] = pack_message(init_msg);
                }
            }
        }
    }

    INIT_C_TO_V_ADDRS:
    for (int addr = 0; addr < EDGE_BANK_DEPTH; addr++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        INIT_C_TO_V_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            c_to_v[bank][addr] = zero_packed_message();
        }
    }

    INIT_MARGINAL_GROUPS:
    for (int j_base = 0; j_base < NUM_FAULTS; j_base += POSTERIOR_BANK_FACTOR) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        INIT_MARGINAL_LANES:
        for (int lane = 0; lane < POSTERIOR_BANK_FACTOR; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int j = j_base + lane;
            if (j < NUM_FAULTS) {
                marginals[j] = (Posterior)read_prior_banked(priors, j);
            }
        }
    }
}

// One leg of DMem-BP within Relay-BP.
inline bool run_dmem_bp_leg(
    PackedMessage    v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    PackedMessage    c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    const Prior      priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    Posterior        marginals[NUM_FAULTS],
    PackedBits       hard_decisions[NUM_FAULT_WORDS],
    BetaInt          beta_int,
    MemShift         mem_shift,
    int              max_iters,
    int&             iters_used
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    bool converged = false;
    iters_used = 0;

    LEG_ITER:
    for (int t = 0; t < max_iters; t++) {
// clang-format off
        #pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_ITERS_PER_LEG
        // clang-format on
        AlphaShift alpha_shift = (t < ALPHA_SHIFT_MAX) ? (AlphaShift)t : (AlphaShift)ALPHA_SHIFT_MAX;
        bool is_first = (t == 0);

        bp_iteration(
            v_to_c, c_to_v, syndrome, priors,
            marginals, hard_decisions,
            alpha_shift, beta_int, mem_shift, is_first);

        iters_used = t + 1;

        if ((((t + 1) % CONVERGENCE_CHECK_INTERVAL) == 0) || ((t + 1) == max_iters)) {
            if (check_convergence(hard_decisions, syndrome)) {
                converged = true;
                break;
            }
        }
    }

    return converged;
}

inline int min_int(int lhs, int rhs) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    return (lhs < rhs) ? lhs : rhs;
}

// Relay-BP-S: the full algorithm.
inline bool relay_bp_decode(
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    const Prior      priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    PackedBits       best_estimate[NUM_FAULT_WORDS],
    int&             total_iters,
    int&             num_solutions_found
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on

    PackedMessage    v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH];
    PackedMessage    c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH];
    Posterior        marginals[NUM_FAULTS];
    PackedBits       hard_decisions[NUM_FAULT_WORDS];
// clang-format off
    #pragma HLS BIND_STORAGE variable=v_to_c         type=ram_t2p impl=bram
    #pragma HLS BIND_STORAGE variable=c_to_v         type=ram_t2p impl=bram
    #pragma HLS BIND_STORAGE variable=marginals      type=ram_2p impl=bram
    #pragma HLS BIND_STORAGE variable=hard_decisions type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=v_to_c         dim=1 type=complete
    #pragma HLS ARRAY_PARTITION variable=c_to_v         dim=1 type=complete
    #pragma HLS ARRAY_PARTITION variable=marginals      dim=1 type=cyclic factor=POSTERIOR_BANK_FACTOR
    #pragma HLS ARRAY_PARTITION variable=hard_decisions dim=1 type=cyclic factor=PACKED_BANK_FACTOR
    // clang-format on

    init_messages(v_to_c, c_to_v, marginals, priors);
    clear_fault_bits(hard_decisions);
    clear_fault_bits(best_estimate);

    WEIGHT best_weight = (WEIGHT)(WEIGHT_MAX);
    num_solutions_found = 0;
    total_iters = 0;

    bool any_solution = false;

    RELAY_LEGS:
    for (int r = 0; r < MAX_LEGS; r++) {
// clang-format off
        #pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_LEGS
        // clang-format on
        if (total_iters >= GLOBAL_MAX_ITERS) {
            break;
        }

        BetaInt beta = LEG_BETA[r];
        int iters_this_leg = 0;
        int remaining_iters = GLOBAL_MAX_ITERS - total_iters;
        int leg_iters = min_int(MAX_ITERS_PER_LEG, remaining_iters);

        bool converged = run_dmem_bp_leg(
            v_to_c, c_to_v, syndrome, priors,
            marginals, hard_decisions, beta,
            MEM_SHIFT, leg_iters, iters_this_leg);

        total_iters += iters_this_leg;

        if (converged) {
            num_solutions_found++;
            any_solution = true;

            WEIGHT w = compute_weight(hard_decisions, priors);

            if (w < best_weight) {
                best_weight = w;
                COPY_BEST:
                for (int word = 0; word < NUM_FAULT_WORDS; word++) {
// clang-format off
                    #pragma HLS PIPELINE II=1
                    // clang-format on
                    best_estimate[word] = hard_decisions[word];
                }
            }
            if (num_solutions_found >= MAX_SOLUTIONS) {
                break;
            }
        }
    }
    return any_solution;
}

#endif
