#ifndef VNU_H
#define VNU_H

#include "constants.h"
#include "types.h"
#include "tools.h"

// Compute the new Lambda_j(t) = (1 - gamma_j) Lambda_j(0) + gamma_j M_j(t-1)
// beta_int ~= (1 - gamma_j) * M_scale
// gamma_int ~= gamma_j * M_scale = M_scale - beta_int
// Lambda_j(t) ~= (beta_int * Lambda_j(0) + gamma_int * M_j(t-1)) / M_scale

inline Posterior compute_dmem_bias(
    Prior       prior_lambda,
    Posterior   prev_marginal,
    BetaInt     beta_int,
    MemShift    mem_shift,
    bool        is_first_iter
) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    if (is_first_iter) {
        // First iteration: just using the prior
        return (Posterior)prior_lambda;
    }

    int M_scale = 1 << mem_shift;
    int gamma_int = M_scale - beta_int;

    int term1 = ((int)beta_int * (int)prior_lambda) >> mem_shift;
    int term2 = (gamma_int * (int)prev_marginal) >> mem_shift;

    int sum = term1 + term2;
    if (sum > POST_MAX) sum = POST_MAX;
    if (sum < POST_MIN) sum = POST_MIN;

    return (Posterior)sum;
}

// Gross-code-scale variable node update.
// Runtime var_idx avoids recursive template instantiation over NUM_FAULTS.
inline void variable_node_unit_runtime(
    int             var_idx,
    const Message   in_msgs[H_MAX_COL_DEGREE],
    Prior           prior_lambda,
    Posterior       prev_marginal,
    BetaInt         beta_int,
    MemShift        mem_shift,
    bool            is_first_iter,
    Message         out_msgs[H_MAX_COL_DEGREE],
    HardDecision&   hard_decision,
    Posterior&      new_marginal
) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    int deg = H_COL_DEGREES[var_idx];

    Posterior lambda_j = compute_dmem_bias(
        prior_lambda, prev_marginal, beta_int, mem_shift, is_first_iter);

    int msg_bias_sum = (int)lambda_j;
    SUM_LOOP_RUNTIME:
    for (int k = 0; k < H_MAX_COL_DEGREE; k++) {
// clang-format off
        #pragma HLS UNROLL
        // clang-format on
        if (k < deg) {
            msg_bias_sum += (int)msg_to_posterior(in_msgs[k]);
        }
    }

    Posterior total_sum;
    if      (msg_bias_sum > POST_MAX) total_sum = POST_MAX;
    else if (msg_bias_sum < POST_MIN) total_sum = POST_MIN;
    else                              total_sum = (Posterior)msg_bias_sum;

    new_marginal = total_sum;
    hard_decision = (total_sum < 0) ? (HardDecision)1 : (HardDecision)0;

    OUT_LOOP_RUNTIME:
    for (int k = 0; k < H_MAX_COL_DEGREE; k++) {
// clang-format off
        #pragma HLS UNROLL
        // clang-format on
        if (k < deg) {
            Posterior excl = sat_sub(total_sum, msg_to_posterior(in_msgs[k]));
            out_msgs[k] = posterior_to_msg(excl);
        } else {
            out_msgs[k].sign = 0;
            out_msgs[k].mag  = 0;
        }
    }
}

#endif
