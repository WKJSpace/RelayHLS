#define main original_testbench_main
#include "testbench/relaybp_tb.cpp"
#undef main
#include <algorithm>
#include <cstdint>
#include <random>

static int floor_div(int value, int divisor) {
    return value >= 0 ? value / divisor : -((-value + divisor - 1) / divisor);
}

static bool arithmetic_contract() {
    for (int prior = 0; prior <= MSG_MAX_MAG; ++prior)
        for (int previous = POST_MIN; previous <= POST_MAX; ++previous)
            for (int leg = 0; leg < MAX_LEGS; ++leg) {
                int expected = floor_div(LEG_BETA[leg] * prior, MEM_SCALE)
                    + floor_div((MEM_SCALE - LEG_BETA[leg]) * previous, MEM_SCALE);
                expected = std::max(POST_MIN, std::min(POST_MAX, expected));
                if ((int)compute_dmem_bias(prior, previous, LEG_BETA[leg], MEM_SHIFT, false) != expected)
                    return false;
                if ((int)compute_dmem_bias(prior, previous, LEG_BETA[leg], MEM_SHIFT, true) != prior)
                    return false;
            }
    return true;
}

static bool leg_carry_contract() {
    static PackedMessage q[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH], r[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH];
    static PackedMessage expected_q[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH], expected_r[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH];
    static Prior banked[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH];
    static Posterior posterior[NUM_FAULTS], expected_posterior[NUM_FAULTS];
    static PackedBits hard[NUM_FAULT_WORDS], expected_hard[NUM_FAULT_WORDS];
    PackedBits syndrome[NUM_DETECTOR_WORDS] = {};
    for (int bank = 0; bank < PRIOR_BANK_FACTOR; ++bank)
        for (int addr = 0; addr < PRIOR_BANK_DEPTH; ++addr) banked[bank][addr] = 5;
    for (int leg = 0; leg < MAX_LEGS; ++leg) {
        init_messages(q, r, posterior, banked);
        init_messages(expected_q, expected_r, expected_posterior, banked);
        clear_fault_bits(hard);
        clear_fault_bits(expected_hard);
        for (int j = 0; j < NUM_FAULTS; ++j) posterior[j] = expected_posterior[j] = -32;
        bp_iteration(expected_q, expected_r, syndrome, banked, expected_posterior,
                     expected_hard, 0, LEG_BETA[leg], MEM_SHIFT, leg == 0);
        int used = 0;
        run_dmem_bp_leg(q, r, syndrome, banked, posterior, hard,
                       LEG_BETA[leg], MEM_SHIFT, 1, leg == 0, used);
        if (used != 1) return false;
        for (int j = 0; j < NUM_FAULTS; ++j)
            if (posterior[j] != expected_posterior[j]) return false;
        for (int word = 0; word < NUM_FAULT_WORDS; ++word)
            if (hard[word] != expected_hard[word]) return false;
        for (int bank = 0; bank < EDGE_BANK_FACTOR; ++bank)
            for (int addr = 0; addr < EDGE_BANK_DEPTH; ++addr)
                if (q[bank][addr] != expected_q[bank][addr] || r[bank][addr] != expected_r[bank][addr])
                    return false;
    }
    return true;
}

static bool stage_contract(const Prior banked[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH]) {
    static PackedMessage q[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH], r[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH];
    static Message raw_q[NUM_EDGES], raw_r[NUM_EDGES];
    static Posterior posterior[NUM_FAULTS], raw_posterior[NUM_FAULTS];
    static PackedBits hard[NUM_FAULT_WORDS], raw_hard[NUM_FAULT_WORDS];
    init_messages(q, r, posterior, banked);
    clear_fault_bits(hard);
    clear_fault_bits(raw_hard);
    for (int edge = 0; edge < NUM_EDGES; ++edge) {
        raw_q[edge].sign = raw_r[edge].sign = 0;
        raw_q[edge].mag = raw_r[edge].mag = 0;
    }
    for (int j = 0; j < NUM_FAULTS; ++j) {
        raw_posterior[j] = priors[j];
        for (int slot = 0; slot < H_COL_DEGREES[j]; ++slot)
            raw_q[EDGE_FOR_VAR_POS[j][slot]].mag = priors[j];
    }
    for (int update = 0; update < MAX_LEGS; ++update) {
        bp_iteration(q, r, syndrome_in, banked, posterior, hard,
                     update, LEG_BETA[update], MEM_SHIFT, update == 0);
        raw_bp_iteration(raw_q, raw_r, syndrome_in, priors, raw_posterior,
                         raw_hard, update, LEG_BETA[update], MEM_SHIFT, update == 0);
        for (int group = 0; group < CNU_EDGE_GROUPS; ++group)
            for (int bank = 0; bank < EDGE_BANK_FACTOR; ++bank)
                for (int port = 0; port < EDGE_BANK_PORTS; ++port)
                    if (CNU_EDGE_VALID[group][bank][port]) {
                        int check = group * CNU_PARALLEL + CNU_EDGE_LANE[group][bank][port];
                        int edge = EDGE_FOR_CHECK_POS[check][CNU_EDGE_SLOT[group][bank][port]];
                        int addr = CNU_EDGE_ADDR[group][bank][port];
                        if (q[bank][addr] != pack_message(raw_q[edge]) || r[bank][addr] != pack_message(raw_r[edge]))
                            return false;
                    }
        for (int j = 0; j < NUM_FAULTS; ++j)
            if (posterior[j] != raw_posterior[j]) return false;
        for (int word = 0; word < NUM_FAULT_WORDS; ++word)
            if (hard[word] != raw_hard[word]) return false;
    }
    return true;
}

int main() {
    if (!arithmetic_contract() || !leg_carry_contract()) {
        std::cerr << "FAIL arithmetic or carried-leg state\n";
        return 1;
    }
    std::mt19937_64 random(20261006);
    static Prior banked[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH];
    static PackedBits candidate[NUM_FAULT_WORDS], best[NUM_FAULT_WORDS], expected_best[NUM_FAULT_WORDS];
    int max_updates = 0;
    int nonzero_frames = 0, nonzero_carries = 0;
    for (int test = 0; test < 32; ++test) {
        for (int j = 0; j < NUM_FAULTS; ++j) {
            priors[j] = test == 0 ? 0 : test == 1 ? MSG_MAX_MAG : random() & MSG_MAX_MAG;
            banked[j % PRIOR_BANK_FACTOR][j / PRIOR_BANK_FACTOR] = priors[j];
        }
        for (int word = 0; word < NUM_DETECTOR_WORDS; ++word)
            syndrome_in[word] = test == 0 ? 0 : random();
        for (int word = 0; word < CARRY_WORDS; ++word)
            carry_in[word] = test < 3 ? 0 : random();
        for (int word = 0; word < NUM_FAULT_WORDS; ++word) candidate[word] = random();
        if (compute_weight(candidate, banked) != raw_compute_weight(candidate, priors)) {
            std::cerr << "FAIL parallel candidate cost\n";
            return 2;
        }
        if (test == 2) raw_compute_h_times_e(candidate, syndrome_in);
        if (!stage_contract(banked)) {
            std::cerr << "FAIL scalar edge messages, posteriors or hard decisions\n";
            return 8;
        }
        int expected_iterations = 0, expected_solutions = 0;
        bool expected_found = raw_relay_bp_decode(syndrome_in, priors, expected_best,
                                                  expected_iterations, expected_solutions);
        int iterations = 0, solutions = 0;
        bool found = relay_bp_decode(syndrome_in, banked, best, iterations, solutions);
        if (found != expected_found || iterations != expected_iterations || solutions != expected_solutions)
            return 3;
        if (iterations > GLOBAL_MAX_ITERS) return 4;
        max_updates = std::max(max_updates, iterations);
        for (int word = 0; word < NUM_FAULT_WORDS; ++word)
            if (best[word] != expected_best[word]) return 5;
        for (int j = 0; j < NUM_FAULTS; ++j)
            if (!H_COL_DEGREES[j] && get_packed_bit(best, j)) return 6;
        pack_priors();
        raw_decode_window();
        nonzero_frames += delta_raw != 0;
        bool nonzero_carry = false;
        for (int word = 0; word < CARRY_WORDS; ++word) nonzero_carry |= carry_raw[word] != 0;
        nonzero_carries += nonzero_carry;
        // Reuse the public top twice to catch state retained between calls.
        for (int repeat = 0; repeat < 2; ++repeat) {
            relaybp_top(syndrome_in, carry_in, prior_words, e_hat_wide,
                        &delta_wide, carry_wide, &iterations_wide, &converged_wide);
            if (!compare_outputs("relaybp_top", e_hat_wide, carry_wide,
                                 delta_wide, iterations_wide, converged_wide)) return 7;
        }
    }
    if (max_updates != GLOBAL_MAX_ITERS) return 9;
#ifdef RELAYHLS_WINDOW_FIXTURE
    if (!nonzero_frames || !nonzero_carries) return 10;
#endif
    std::cout << "PASS: 128 scalar BP updates, 32 scalar controller cases, 64 full-top calls, four carried-leg checks, "
              << "exhaustive bias arithmetic; maximum updates=" << max_updates << '\n';
    return 0;
}
