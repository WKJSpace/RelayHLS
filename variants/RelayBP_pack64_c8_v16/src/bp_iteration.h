#ifndef BP_ITERATION_H
#define BP_ITERATION_H

#include "types.h"
#include "cnu.h"
#include "vnu.h"
#include "constants.h"
#include "packed_bits.h"

static_assert(EDGE_BANK_PORTS == 2, "cnu_pass/vnu_pass require dual-port message banks");
static_assert((PACK_BITS % VNU_PARALLEL) == 0, "VNU_PARALLEL must divide PACK_BITS");

inline void cnu_pass(
    const PackedMessage v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    AlphaShift       alpha_shift,
    PackedMessage    c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH]
) {
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS DEPENDENCE variable=v_to_c inter false
    #pragma HLS DEPENDENCE variable=v_to_c intra false
    #pragma HLS DEPENDENCE variable=c_to_v inter false
    #pragma HLS DEPENDENCE variable=c_to_v intra false
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_LANE  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_LANE  dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_SLOT  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_SLOT  dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_ADDR  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_ADDR  dim=3 type=complete
    // clang-format on

    CNU_ROW_GROUPS:
    for (int i_base = 0; i_base < NUM_DETECTORS; i_base += CNU_PARALLEL) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        Message in[CNU_PARALLEL][H_MAX_ROW_DEGREE];
        Message out[CNU_PARALLEL][H_MAX_ROW_DEGREE];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=in  dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=in  dim=2 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=2 type=complete
        // clang-format on

        CNU_CLEAR_LANES:
        for (int lane = 0; lane < CNU_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            CNU_CLEAR_SLOTS:
            for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                in[lane][k].sign = 0;
                in[lane][k].mag = 0;
            }
        }

        int group = i_base / CNU_PARALLEL;
        CNU_GATHER_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            CNU_GATHER_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (CNU_EDGE_VALID[group][bank][port]) {
                    int lane = CNU_EDGE_LANE[group][bank][port];
                    int slot = CNU_EDGE_SLOT[group][bank][port];
                    int addr = CNU_EDGE_ADDR[group][bank][port];
                    in[lane][slot] = unpack_message(v_to_c[bank][addr]);
                }
            }
        }

        CNU_COMPUTE_LANES:
        for (int lane = 0; lane < CNU_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int i = i_base + lane;
            if (i < NUM_DETECTORS) {
                Syndrome syndrome_bit = (Syndrome)get_packed_bit(syndrome, i);
                check_node_unit_runtime(i, in[lane], syndrome_bit, alpha_shift, out[lane]);
            }
        }

        CNU_SCATTER_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            CNU_SCATTER_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (CNU_EDGE_VALID[group][bank][port]) {
                    int lane = CNU_EDGE_LANE[group][bank][port];
                    int slot = CNU_EDGE_SLOT[group][bank][port];
                    int addr = CNU_EDGE_ADDR[group][bank][port];
                    c_to_v[bank][addr] = pack_message(out[lane][slot]);
                }
            }
        }
    }
}

inline void vnu_pass(
    const PackedMessage c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    const Prior         priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    Posterior           marginals[NUM_FAULTS],
    BetaInt             beta_int,
    MemShift            mem_shift,
    bool                is_first_iter,
    PackedMessage       v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    PackedBits          hard_decisions[NUM_FAULT_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS DEPENDENCE variable=c_to_v inter false
    #pragma HLS DEPENDENCE variable=c_to_v intra false
    #pragma HLS DEPENDENCE variable=v_to_c inter false
    #pragma HLS DEPENDENCE variable=v_to_c intra false
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_LANE  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_LANE  dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_SLOT  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_SLOT  dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_ADDR  dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_ADDR  dim=3 type=complete
    // clang-format on

    // Flattened single-pipeline VNU: one continuous pipeline over all
    // VNU_EDGE_GROUPS groups.  Each group processes VNU_PARALLEL lanes and
    // issues at most EDGE_BANK_PORTS accesses per bank.
    constexpr int GROUPS_PER_WORD = PACK_BITS / VNU_PARALLEL;

    ap_uint<PACK_BITS> hd_word_acc = 0;

    VNU_GROUPS:
    for (int group = 0; group < VNU_EDGE_GROUPS; group++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        Message in[VNU_PARALLEL][H_MAX_COL_DEGREE];
        Message out[VNU_PARALLEL][H_MAX_COL_DEGREE];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=in  dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=in  dim=2 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=2 type=complete
        // clang-format on

        VNU_CLEAR_LANES:
        for (int lane = 0; lane < VNU_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            VNU_CLEAR_SLOTS:
            for (int k = 0; k < H_MAX_COL_DEGREE; k++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                in[lane][k].sign = 0;
                in[lane][k].mag = 0;
            }
        }

        VNU_GATHER_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            VNU_GATHER_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (VNU_EDGE_VALID[group][bank][port]) {
                    int lane = VNU_EDGE_LANE[group][bank][port];
                    int slot = VNU_EDGE_SLOT[group][bank][port];
                    int addr = VNU_EDGE_ADDR[group][bank][port];
                    in[lane][slot] = unpack_message(c_to_v[bank][addr]);
                }
            }
        }

        ap_uint<VNU_PARALLEL> hd_group = 0;

        VNU_COMPUTE_LANES:
        for (int lane = 0; lane < VNU_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int j = group * VNU_PARALLEL + lane;
            if ((j < NUM_FAULTS) && (H_COL_DEGREES[j] > 0)) {
                HardDecision hd;
                Posterior nm;
                int prior_bank = j % PRIOR_BANK_FACTOR;
                int prior_addr = j / PRIOR_BANK_FACTOR;
                variable_node_unit_runtime(
                    j, in[lane], priors[prior_bank][prior_addr], marginals[j],
                    beta_int, mem_shift, is_first_iter,
                    out[lane], hd, nm);

                hd_group[lane] = hd;
                marginals[j] = nm;
            }
        }

        VNU_SCATTER_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            VNU_SCATTER_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (VNU_EDGE_VALID[group][bank][port]) {
                    int lane = VNU_EDGE_LANE[group][bank][port];
                    int slot = VNU_EDGE_SLOT[group][bank][port];
                    int addr = VNU_EDGE_ADDR[group][bank][port];
                    v_to_c[bank][addr] = pack_message(out[lane][slot]);
                }
            }
        }

        // Assemble packed hard-decision words: GROUPS_PER_WORD consecutive
        // groups fill one PACK_BITS word.  Each group writes a disjoint
        // VNU_PARALLEL-bit slice of a carried accumulator, so there is no
        // packed-memory read-modify-write. II=1 is a synthesis request.
        int word_slot = group % GROUPS_PER_WORD;
        hd_word_acc.range((word_slot + 1) * VNU_PARALLEL - 1, word_slot * VNU_PARALLEL) = hd_group;
        if (word_slot == (GROUPS_PER_WORD - 1)) {
            hard_decisions[group / GROUPS_PER_WORD] = (PackedBits)hd_word_acc;
        }
    }
}

// One full BP iteration: CNU pass followed by VNU pass.
inline void bp_iteration(
    PackedMessage       v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    PackedMessage       c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    const PackedBits    syndrome[NUM_DETECTOR_WORDS],
    const Prior         priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    Posterior           marginals[NUM_FAULTS],
    PackedBits          hard_decisions[NUM_FAULT_WORDS],
    AlphaShift          alpha_shift,
    BetaInt             beta_int,
    MemShift            mem_shift,
    bool                is_first_iter
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on

    cnu_pass(v_to_c, syndrome, alpha_shift, c_to_v);

    vnu_pass(
        c_to_v, priors, marginals,
        beta_int, mem_shift, is_first_iter,
        v_to_c, hard_decisions);
}

// Convergence check: verify H_tilde * e_hat = sigma.
inline bool check_convergence(
    const PackedBits hard_decisions[NUM_FAULT_WORDS],
    const PackedBits syndrome[NUM_DETECTOR_WORDS]
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
    HardDecision hd_banks[PACKED_BANK_FACTOR][PRIOR_BANK_DEPTH];
// clang-format off
    #pragma HLS BIND_STORAGE variable=hd_banks type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=hd_banks dim=1 type=complete
    // clang-format on
    unpack_packed_bits_banked(hard_decisions, hd_banks);

    bool any_mismatch = false;

    CHECK_GROUPS:
    for (int i_base = 0; i_base < NUM_DETECTORS; i_base += CONVERGENCE_PARALLEL) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        bool mismatch[CONVERGENCE_PARALLEL];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=mismatch dim=1 type=complete
        // clang-format on

        CHECK_LANES:
        for (int lane = 0; lane < CONVERGENCE_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            mismatch[lane] = false;
        }

        Syndrome parity[CONVERGENCE_PARALLEL];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=parity dim=1 type=complete
        // clang-format on
        CHECK_INIT_PARITY:
        for (int lane = 0; lane < CONVERGENCE_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            parity[lane] = 0;
        }

        int group = i_base / CONVERGENCE_PARALLEL;
        CHECK_BANKS:
        for (int bank = 0; bank < PACKED_BANK_FACTOR; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            CHECK_PORTS:
            for (int port = 0; port < DET_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (DET_EDGE_VALID[group][bank][port]) {
                    int lane = DET_EDGE_LANE[group][bank][port];
                    int addr = DET_EDGE_ADDR[group][bank][port];
                    parity[lane] ^= hd_banks[bank][addr];
                }
            }
        }

        CHECK_COMPARE:
        for (int lane = 0; lane < CONVERGENCE_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int i = i_base + lane;
            if (i < NUM_DETECTORS) {
                mismatch[lane] = (parity[lane] != (Syndrome)get_packed_bit(syndrome, i));
            } else {
                mismatch[lane] = false;
            }
        }

        CHECK_REDUCE:
        for (int lane = 0; lane < CONVERGENCE_PARALLEL; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            any_mismatch |= mismatch[lane];
        }
    }
    return !any_mismatch;
}

#endif
