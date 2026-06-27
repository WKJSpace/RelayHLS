#include "../src/decoder_top.h"
#include "../src/tools.h"

#include <iostream>

static PackedBits   syndrome_in[NUM_DETECTOR_WORDS];
static PackedBits   carry_in[CARRY_WORDS];
static Prior        priors[NUM_FAULTS];
static PackedPriors prior_words[NUM_PRIOR_WORDS];

static PackedBits   e_hat_raw[NUM_FAULT_WORDS];
static PackedBits   carry_raw[CARRY_WORDS];
static PauliFrame   delta_raw;
static int          iterations_raw;
static bool         converged_raw;

static PackedBits   e_hat_wide[NUM_FAULT_WORDS];
static PackedBits   carry_wide[CARRY_WORDS];
static PauliFrame   delta_wide;
static int          iterations_wide;
static bool         converged_wide;

static void fill_inputs() {
    for (int word = 0; word < NUM_DETECTOR_WORDS; word++) {
        syndrome_in[word] = (word * 0x9e3779b97f4a7c15ULL) ^ 0x0123456789abcdefULL;
    }

    for (int word = 0; word < CARRY_WORDS; word++) {
        carry_in[word] = (word * 0x100000001b3ULL) ^ 0xf0f0f0f0f0f0f0f0ULL;
    }

    for (int j = 0; j < NUM_FAULTS; j++) {
        priors[j] = (Prior)((j * 7 + 3) & MSG_MAX_MAG);
    }
}

static void pack_priors() {
    for (int word = 0; word < NUM_PRIOR_WORDS; word++) {
        PackedPriors packed = 0;

        for (int lane = 0; lane < PRIOR_PACK_FACTOR; lane++) {
            const int j = word * PRIOR_PACK_FACTOR + lane;
            if (j < NUM_FAULTS) {
                packed.range((lane + 1) * MSG_INT_BITS - 1, lane * MSG_INT_BITS) = priors[j];
            }
        }

        prior_words[word] = packed;
    }
}

static MsgMagnitude raw_apply_alpha(MsgMagnitude mag, AlphaShift alpha_shift) {
    if (alpha_shift == 0) {
        return mag;
    }

    return sat_mag((int)mag - (int)(mag >> alpha_shift));
}

static Posterior raw_compute_dmem_bias(
    Prior     prior_lambda,
    Posterior prev_marginal,
    BetaInt   beta_int,
    MemShift  mem_shift,
    bool      is_first_iter
) {
    if (is_first_iter) {
        return (Posterior)prior_lambda;
    }

    int m_scale = 1 << mem_shift;
    int gamma_int = m_scale - beta_int;
    int sum = (((int)beta_int * (int)prior_lambda) >> mem_shift)
            + ((gamma_int * (int)prev_marginal) >> mem_shift);

    if (sum > POST_MAX) {
        sum = POST_MAX;
    }
    if (sum < POST_MIN) {
        sum = POST_MIN;
    }
    return (Posterior)sum;
}

static void raw_check_node_unit(
    int              check_idx,
    Message          v_to_c[NUM_EDGES],
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    AlphaShift       alpha_shift,
    Message          c_to_v[NUM_EDGES]
) {
    int deg = H_ROW_DEGREES[check_idx];
    MsgSign total_parity = (Syndrome)get_packed_bit(syndrome, check_idx);
    MsgMagnitude min1 = MSG_MAX_MAG;
    MsgMagnitude min2 = MSG_MAX_MAG;
    int min1_pos = 0;

    for (int k = 0; k < deg; k++) {
        int edge = EDGE_FOR_CHECK_POS[check_idx][k];
        Message msg = v_to_c[edge];
        total_parity ^= msg.sign;

        if (msg.mag < min1) {
            min2 = min1;
            min1 = msg.mag;
            min1_pos = k;
        } else if (msg.mag < min2) {
            min2 = msg.mag;
        }
    }

    MsgMagnitude min1_scaled = raw_apply_alpha(min1, alpha_shift);
    MsgMagnitude min2_scaled = raw_apply_alpha(min2, alpha_shift);

    for (int k = 0; k < deg; k++) {
        int edge = EDGE_FOR_CHECK_POS[check_idx][k];
        c_to_v[edge].sign = total_parity ^ v_to_c[edge].sign;
        c_to_v[edge].mag = (k == min1_pos) ? min2_scaled : min1_scaled;
    }
}

static void raw_variable_node_unit(
    int         var_idx,
    Message     c_to_v[NUM_EDGES],
    const Prior local_priors[NUM_FAULTS],
    Posterior   marginals[NUM_FAULTS],
    BetaInt     beta_int,
    MemShift    mem_shift,
    bool        is_first_iter,
    Message     v_to_c[NUM_EDGES],
    PackedBits  hard_decisions[NUM_FAULT_WORDS]
) {
    int deg = H_COL_DEGREES[var_idx];
    if (deg == 0) {
        set_packed_bit(hard_decisions, var_idx, (HardDecision)0);
        return;
    }

    Posterior lambda_j = raw_compute_dmem_bias(
        local_priors[var_idx], marginals[var_idx],
        beta_int, mem_shift, is_first_iter);
    int msg_bias_sum = (int)lambda_j;

    for (int k = 0; k < deg; k++) {
        int edge = EDGE_FOR_VAR_POS[var_idx][k];
        msg_bias_sum += (int)msg_to_posterior(c_to_v[edge]);
    }

    Posterior total_sum;
    if (msg_bias_sum > POST_MAX) {
        total_sum = POST_MAX;
    } else if (msg_bias_sum < POST_MIN) {
        total_sum = POST_MIN;
    } else {
        total_sum = (Posterior)msg_bias_sum;
    }

    marginals[var_idx] = total_sum;
    set_packed_bit(hard_decisions, var_idx, (total_sum < 0) ? (HardDecision)1 : (HardDecision)0);

    for (int k = 0; k < deg; k++) {
        int edge = EDGE_FOR_VAR_POS[var_idx][k];
        Posterior excl = sat_sub(total_sum, msg_to_posterior(c_to_v[edge]));
        v_to_c[edge] = posterior_to_msg(excl);
    }
}

static void raw_bp_iteration(
    Message          v_to_c[NUM_EDGES],
    Message          c_to_v[NUM_EDGES],
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    const Prior      local_priors[NUM_FAULTS],
    Posterior        marginals[NUM_FAULTS],
    PackedBits       hard_decisions[NUM_FAULT_WORDS],
    AlphaShift       alpha_shift,
    BetaInt          beta_int,
    MemShift         mem_shift,
    bool             is_first_iter
) {
    for (int i = 0; i < NUM_DETECTORS; i++) {
        raw_check_node_unit(i, v_to_c, syndrome, alpha_shift, c_to_v);
    }

    for (int j = 0; j < NUM_FAULTS; j++) {
        raw_variable_node_unit(
            j, c_to_v, local_priors, marginals,
            beta_int, mem_shift, is_first_iter,
            v_to_c, hard_decisions);
    }
}

static bool raw_check_convergence(
    const PackedBits hard_decisions[NUM_FAULT_WORDS],
    const PackedBits syndrome[NUM_DETECTOR_WORDS]
) {
    for (int i = 0; i < NUM_DETECTORS; i++) {
        Syndrome parity = 0;

        for (int k = 0; k < H_ROW_DEGREES[i]; k++) {
            int var_idx = H_ROW_NEIGHBORS[i][k];
            parity ^= (HardDecision)get_packed_bit(hard_decisions, var_idx);
        }

        if (parity != (Syndrome)get_packed_bit(syndrome, i)) {
            return false;
        }
    }
    return true;
}

static void raw_clear_fault_bits(PackedBits words[NUM_FAULT_WORDS]) {
    for (int word = 0; word < NUM_FAULT_WORDS; word++) {
        words[word] = 0;
    }
}

static WEIGHT raw_compute_weight(
    const PackedBits hard_decisions[NUM_FAULT_WORDS],
    const Prior      local_priors[NUM_FAULTS]
) {
    WEIGHT weight = 0;

    for (int active = 0; active < NUM_ACTIVE_FAULTS; active++) {
        int j = ACTIVE_FAULT_INDEX[active];
        if (get_packed_bit(hard_decisions, j)) {
            weight += (WEIGHT)local_priors[j];
        }
    }
    return weight;
}

static bool raw_relay_bp_decode(
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    const Prior      local_priors[NUM_FAULTS],
    PackedBits       best_estimate[NUM_FAULT_WORDS],
    int&             total_iters,
    int&             num_solutions_found
) {
    Message    v_to_c[NUM_EDGES];
    Message    c_to_v[NUM_EDGES];
    Posterior  marginals[NUM_FAULTS];
    PackedBits hard_decisions[NUM_FAULT_WORDS];

    for (int edge = 0; edge < NUM_EDGES; edge++) {
        v_to_c[edge].sign = 0;
        v_to_c[edge].mag = 0;
        c_to_v[edge].sign = 0;
        c_to_v[edge].mag = 0;
    }

    for (int j = 0; j < NUM_FAULTS; j++) {
        marginals[j] = (Posterior)local_priors[j];

        for (int k = 0; k < H_COL_DEGREES[j]; k++) {
            int edge = EDGE_FOR_VAR_POS[j][k];
            v_to_c[edge].sign = 0;
            v_to_c[edge].mag = local_priors[j];
        }
    }

    raw_clear_fault_bits(hard_decisions);
    raw_clear_fault_bits(best_estimate);

    WEIGHT best_weight = (WEIGHT)WEIGHT_MAX;
    num_solutions_found = 0;
    total_iters = 0;
    bool any_solution = false;

    for (int r = 0; r < MAX_LEGS; r++) {
        if (total_iters >= GLOBAL_MAX_ITERS) {
            break;
        }

        bool converged = false;
        int remaining_iters = GLOBAL_MAX_ITERS - total_iters;
        int leg_iters = (MAX_ITERS_PER_LEG < remaining_iters) ? MAX_ITERS_PER_LEG : remaining_iters;

        for (int t = 0; t < leg_iters; t++) {
            AlphaShift alpha_shift = (t < ALPHA_SHIFT_MAX) ? (AlphaShift)t : (AlphaShift)ALPHA_SHIFT_MAX;

            raw_bp_iteration(
                v_to_c, c_to_v, syndrome, local_priors,
                marginals, hard_decisions,
                alpha_shift, LEG_BETA[r], MEM_SHIFT, t == 0);

            total_iters++;

            if ((((t + 1) % CONVERGENCE_CHECK_INTERVAL) == 0) || ((t + 1) == leg_iters)) {
                if (raw_check_convergence(hard_decisions, syndrome)) {
                    converged = true;
                    break;
                }
            }
        }

        if (converged) {
            num_solutions_found++;
            any_solution = true;

            WEIGHT weight = raw_compute_weight(hard_decisions, local_priors);
            if (weight < best_weight) {
                best_weight = weight;
                for (int word = 0; word < NUM_FAULT_WORDS; word++) {
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

static PauliFrame raw_compute_a_times_e(const PackedBits e[NUM_FAULT_WORDS]) {
    PauliFrame delta_f = 0;

    for (int k = 0; k < K_OBSERVABLES; k++) {
        Syndrome parity = 0;

        for (int idx = 0; idx < A_ROW_DEGREES[k]; idx++) {
            int var_idx = A_ROW_NEIGHBORS[k][idx];
            parity ^= (HardDecision)get_packed_bit(e, var_idx);
        }

        if (parity) {
            delta_f = delta_f | ((PauliFrame)1 << k);
        }
    }
    return delta_f;
}

static void raw_compute_h_times_e(
    const PackedBits e[NUM_FAULT_WORDS],
    PackedBits       delta_d[NUM_DETECTOR_WORDS]
) {
    for (int word = 0; word < NUM_DETECTOR_WORDS; word++) {
        delta_d[word] = 0;
    }

    for (int i = 0; i < NUM_DETECTORS; i++) {
        Syndrome parity = 0;

        for (int k = 0; k < H_ROW_DEGREES[i]; k++) {
            int var_idx = H_ROW_NEIGHBORS[i][k];
            parity ^= (HardDecision)get_packed_bit(e, var_idx);
        }

        set_packed_bit(delta_d, i, parity);
    }
}

static void raw_decode_window() {
    PackedBits window_syndrome[NUM_DETECTOR_WORDS];
    PackedBits e_committed[NUM_FAULT_WORDS];
    PackedBits delta_d[NUM_DETECTOR_WORDS];
    int num_solutions_found = 0;

    for (int word = 0; word < NUM_DETECTOR_WORDS; word++) {
        window_syndrome[word] = syndrome_in[word];
    }

    for (int m = 0; m < M_PER_CYCLE; m++) {
        Syndrome updated = (Syndrome)(get_packed_bit(window_syndrome, m) ^ get_packed_bit(carry_in, m));
        set_packed_bit(window_syndrome, m, updated);
    }

    converged_raw = raw_relay_bp_decode(
        window_syndrome, priors, e_hat_raw,
        iterations_raw, num_solutions_found);

    raw_clear_fault_bits(e_committed);
    for (int j = 0; j < NUM_FAULTS; j++) {
        HardDecision bit = get_packed_bit(e_hat_raw, j) & (HardDecision)COMMIT_MASK[j];
        set_packed_bit(e_committed, j, bit);
    }

    delta_raw = raw_compute_a_times_e(e_committed);
    raw_compute_h_times_e(e_committed, delta_d);

    for (int word = 0; word < CARRY_WORDS; word++) {
        carry_raw[word] = 0;
    }

    for (int m = 0; m < M_PER_CYCLE; m++) {
        set_packed_bit(carry_raw, m, get_packed_bit(delta_d, CARRY_DETECTOR_START + m));
    }
}

static bool compare_outputs(
    const char*      name,
    const PackedBits e_hat[NUM_FAULT_WORDS],
    const PackedBits carry[CARRY_WORDS],
    PauliFrame       delta_f,
    int              iterations,
    bool             converged
) {
    bool ok = true;

    if (delta_raw != delta_f) {
        std::cout << "ERROR: " << name << " delta_f mismatch: raw=" << delta_raw
                  << " dut=" << delta_f << "\n";
        ok = false;
    }

    if (iterations_raw != iterations) {
        std::cout << "ERROR: " << name << " iterations mismatch: raw=" << iterations_raw
                  << " dut=" << iterations << "\n";
        ok = false;
    }

    if (converged_raw != converged) {
        std::cout << "ERROR: " << name << " converged mismatch: raw=" << converged_raw
                  << " dut=" << converged << "\n";
        ok = false;
    }

    for (int word = 0; word < NUM_FAULT_WORDS; word++) {
        if (e_hat_raw[word] != e_hat[word]) {
            std::cout << "ERROR: " << name << " e_hat mismatch at word " << word
                      << ": raw=" << e_hat_raw[word]
                      << " dut=" << e_hat[word] << "\n";
            ok = false;
            break;
        }
    }

    for (int word = 0; word < CARRY_WORDS; word++) {
        if (carry_raw[word] != carry[word]) {
            std::cout << "ERROR: " << name << " carry mismatch at word " << word
                      << ": raw=" << carry_raw[word]
                      << " dut=" << carry[word] << "\n";
            ok = false;
            break;
        }
    }

    return ok;
}

int main() {
    fill_inputs();
    pack_priors();
    raw_decode_window();

    relaybp_top(
        syndrome_in, carry_in, prior_words,
        e_hat_wide, &delta_wide, carry_wide,
        &iterations_wide, &converged_wide);

    bool ok = compare_outputs(
        "relaybp_top", e_hat_wide, carry_wide,
        delta_wide, iterations_wide, converged_wide);

    if (!ok) {
        return 1;
    }

    std::cout << "PASS relaybp_tb\n";
    return 0;
}
