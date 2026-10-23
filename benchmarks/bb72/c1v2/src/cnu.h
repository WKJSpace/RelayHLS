#ifndef CNU_H
#define CNU_H

#include "constants.h"
#include "types.h"
#include "tools.h"

// α compensates for min-sum overestimation.
// result = mag * (1 - 2^(-t))
inline MsgMagnitude apply_alpha(MsgMagnitude mag, AlphaShift alpha_shift) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on

    if (alpha_shift == 0) return mag;

    int reduction = mag >> alpha_shift;
    int result    = (int)mag - reduction;

    return sat_mag(result);
}


// ================================================================
// Runtime-indexed Check Node Update
// ================================================================
// check_idx is a runtime row index:
//   0 <= check_idx < NUM_DETECTORS
// in_msgs/out_msgs still have fixed maximum degree:
//   H_MAX_ROW_DEGREE
// Only first DEG entries are valid.

inline void     check_node_unit_runtime(
    int             check_idx,
    const Message   in_msgs[H_MAX_ROW_DEGREE],
    Syndrome        syndrome_bit,
    AlphaShift      alpha_shift,
    Message         out_msgs[H_MAX_ROW_DEGREE]
) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on

    int deg = H_ROW_DEGREES[check_idx];

    MsgSign total_parity = syndrome_bit;

    PARITY_LOOP:
    for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
// clang-format off
        #pragma HLS UNROLL
        // clang-format on
        if (k < deg) {
            total_parity ^= in_msgs[k].sign;
        }
    }

    MinPair leaves[H_MAX_ROW_DEGREE];
// clang-format off
    #pragma HLS ARRAY_PARTITION variable=leaves complete dim=1
    // clang-format on

    BUILD_LEAVES:
    for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
// clang-format off
        #pragma HLS UNROLL
        // clang-format on
        if (k < deg) {
            leaves[k] = make_leaf(in_msgs[k].mag, k);
        } else {
            leaves[k] = make_leaf(MSG_MAX_MAG, k);
        }
    }

    MinPair result = TreeReduce<H_MAX_ROW_DEGREE>::apply(leaves);

    MsgMagnitude min1 = result.min1;
    MsgMagnitude min2 = result.min2;
    int min1_idx = result.min1_idx;

    MsgMagnitude min1_scaled = apply_alpha(min1, alpha_shift);
    MsgMagnitude min2_scaled = apply_alpha(min2, alpha_shift);

    OUTPUT_LOOP:
    for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
// clang-format off
        #pragma HLS UNROLL
        // clang-format on
        if (k < deg) {
            out_msgs[k].sign = total_parity ^ in_msgs[k].sign;
            out_msgs[k].mag  = (k == min1_idx) ? min2_scaled : min1_scaled;
        } else {
            out_msgs[k].sign = 0;
            out_msgs[k].mag  = 0;
        }
    }
}

#endif
