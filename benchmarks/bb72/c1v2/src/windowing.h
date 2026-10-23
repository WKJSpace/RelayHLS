#ifndef WINDOWING_H
#define WINDOWING_H

#include "types.h"
#include "constants.h"
#include "packed_bits.h"
#include "relay_bp.h"

// Apply carry_in to the first cycle of the window.
inline void apply_carry(
    PackedBits       window_syndrome[NUM_DETECTOR_WORDS],
    const PackedBits carry_u[CARRY_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    CARRY_LOOP:
    for (int m = 0; m < M_PER_CYCLE; m++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        Syndrome updated = (Syndrome)(get_packed_bit(window_syndrome, m) ^ get_packed_bit(carry_u, m));
        set_packed_bit(window_syndrome, m, updated);
    }
}

// Mask the decoded estimate down to the commit region.
inline void apply_commit_mask(
    const PackedBits e_hat[NUM_FAULT_WORDS],
    PackedBits       e_committed[NUM_FAULT_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    MASK_WORDS:
    for (int word = 0; word < NUM_FAULT_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        PackedBits in_word = e_hat[word];
        PackedBits out_word = 0;

        MASK_LANES:
        for (int bit = 0; bit < PACK_BITS; bit++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int j = word * PACK_BITS + bit;
            if (j < NUM_FAULTS) {
                out_word[bit] = in_word[bit] & (HardDecision)COMMIT_MASK[j];
            }
        }
        e_committed[word] = out_word;
    }
}

// Producing the predicted detector pattern with delta_d = H_tilde * e.
inline void compute_h_times_e(
    const PackedBits e[NUM_FAULT_WORDS],
    PackedBits       delta_d[NUM_DETECTOR_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS ARRAY_PARTITION variable=DET_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=DET_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=DET_EDGE_LANE  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=DET_EDGE_LANE  dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=DET_EDGE_ADDR   dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=DET_EDGE_ADDR   dim=3 type=complete
    // clang-format on
    HardDecision e_banks[PACKED_BANK_FACTOR][PRIOR_BANK_DEPTH];
    Syndrome delta_banks[PACKED_BANK_FACTOR][PRIOR_BANK_DEPTH];
// clang-format off
    #pragma HLS BIND_STORAGE variable=e_banks type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=e_banks dim=1 type=complete
    #pragma HLS BIND_STORAGE variable=delta_banks type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=delta_banks dim=1 type=complete
    // clang-format on
    unpack_packed_bits_banked(e, e_banks);

    DETECTOR_GROUPS:
    for (int i_base = 0; i_base < NUM_DETECTORS; i_base += CONVERGENCE_PARALLEL) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        Syndrome parity[CONVERGENCE_PARALLEL];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=parity dim=1 type=complete
        // clang-format on

        DETECTOR_CLEAR:
        for (int lane = 0; lane < CONVERGENCE_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            parity[lane] = 0;
        }

        int group = i_base / CONVERGENCE_PARALLEL;
        DETECTOR_BANKS:
        for (int bank = 0; bank < PACKED_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            DETECTOR_PORTS:
            for (int port = 0; port < DET_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (DET_EDGE_VALID[group][bank][port]) {
                    int lane = DET_EDGE_LANE[group][bank][port];
                    int addr = DET_EDGE_ADDR[group][bank][port];
                    parity[lane] ^= e_banks[bank][addr];
                }
            }
        }

        DETECTOR_STORE:
        for (int lane = 0; lane < CONVERGENCE_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int i = i_base + lane;
            if (i < NUM_DETECTORS) {
                delta_banks[i % PACKED_BANK_FACTOR][i / PACKED_BANK_FACTOR] = parity[lane];
            }
        }
    }

    PACK_DETECTOR_WORDS:
    for (int word = 0; word < NUM_DETECTOR_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        PackedBits packed = 0;

        PACK_DETECTOR_LANES:
        for (int lane = 0; lane < PACK_BITS; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int i = word * PACK_BITS + lane;
            if (i < NUM_DETECTORS) {
                packed[lane] = delta_banks[lane][word];
            }
        }
        delta_d[word] = packed;
    }
}

// Extract carry-out u from delta_d.
inline void extract_carry(
    const PackedBits delta_d[NUM_DETECTOR_WORDS],
    PackedBits       carry_out[CARRY_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    INIT_CARRY_WORDS:
    for (int word = 0; word < CARRY_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        carry_out[word] = 0;
    }

    EXTRACT_LOOP:
    for (int m = 0; m < M_PER_CYCLE; m++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        set_packed_bit(carry_out, m, get_packed_bit(delta_d, CARRY_DETECTOR_START + m));
    }
}

// Logical Pauli frame update: delta_f = A_tilde * e_committed (mod 2).
inline PauliFrame compute_a_times_e(
    const PackedBits e[NUM_FAULT_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    PauliFrame delta_f = 0;

    OBS_LOOP:
    for (int k = 0; k < K_OBSERVABLES; k++) {
        Syndrome parity = 0;
        A_XOR_LOOP:
        for (int idx = 0; idx < A_MAX_ROW_DEGREE; idx++) {
// clang-format off
            #pragma HLS PIPELINE II=1
            #pragma HLS LOOP_TRIPCOUNT min=0 max=A_MAX_ROW_DEGREE
            // clang-format on
            if (idx < A_ROW_DEGREES[k]) {
                int var_idx = A_ROW_NEIGHBORS[k][idx];
                parity ^= (HardDecision)get_packed_bit(e, var_idx);
            }
        }
        if (parity) {
            delta_f = delta_f | ((PauliFrame)1 << k);
        }
    }
    return delta_f;
}

struct WindowResult {
    PauliFrame  delta_f;
    PackedBits  carry_out[CARRY_WORDS];
    bool        converged;
    int         iterations_used;
};

// Decode a single window. The raw e_hat is written to the caller-provided array.
inline WindowResult decode_window(
    PackedBits       window_syndrome[NUM_DETECTOR_WORDS],
    const PackedBits carry_in[CARRY_WORDS],
    const Prior      priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    PackedBits       e_hat_out[NUM_FAULT_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    WindowResult result;
// clang-format off
    #pragma HLS ARRAY_PARTITION variable=result.carry_out dim=1 type=complete
    // clang-format on

    apply_carry(window_syndrome, carry_in);

    int total_iters = 0;
    int num_sols = 0;

    result.converged = relay_bp_decode(
        window_syndrome, priors, e_hat_out,
        total_iters, num_sols);

    result.iterations_used = total_iters;

    PackedBits e_committed[NUM_FAULT_WORDS];
    PackedBits delta_d[NUM_DETECTOR_WORDS];
// clang-format off
    #pragma HLS BIND_STORAGE variable=e_committed type=ram_2p impl=bram
    #pragma HLS BIND_STORAGE variable=delta_d      type=ram_2p impl=bram
    // clang-format on

    apply_commit_mask(e_hat_out, e_committed);
    result.delta_f = compute_a_times_e(e_committed);
    compute_h_times_e(e_committed, delta_d);
    extract_carry(delta_d, result.carry_out);

    return result;
}

#endif
