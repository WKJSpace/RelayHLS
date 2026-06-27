#include "decoder_top.h"

static void load_syndrome_words(
    const PackedBits in[NUM_DETECTOR_WORDS],
    PackedBits       local[NUM_DETECTOR_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    LOAD_SYNDROME:
    for (int word = 0; word < NUM_DETECTOR_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        local[word] = in[word];
    }
}

static void load_carry_words(
    const PackedBits in[CARRY_WORDS],
    PackedBits       local[CARRY_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    LOAD_CARRY:
    for (int word = 0; word < CARRY_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        local[word] = in[word];
    }
}

static void load_priors(
    const PackedPriors in[NUM_PRIOR_WORDS],
    Prior              local[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    LOAD_PRIOR_WORDS:
    for (int word = 0; word < NUM_PRIOR_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        PackedPriors packed = in[word];

        PRIOR_LANES:
        for (int lane = 0; lane < PRIOR_PACK_FACTOR; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            const int j = word * PRIOR_PACK_FACTOR + lane;
            if (j < NUM_FAULTS) {
                local[j % PRIOR_BANK_FACTOR][j / PRIOR_BANK_FACTOR] =
                    packed.range((lane + 1) * MSG_INT_BITS - 1, lane * MSG_INT_BITS);
            }
        }
    }
}

static void store_carry_words(
    const PackedBits local[CARRY_WORDS],
    PackedBits       out[CARRY_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    STORE_CARRY:
    for (int word = 0; word < CARRY_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        out[word] = local[word];
    }
}

static void store_e_hat_words(
    const PackedBits local[NUM_FAULT_WORDS],
    PackedBits       out[NUM_FAULT_WORDS]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    STORE_EHAT:
    for (int word = 0; word < NUM_FAULT_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        out[word] = local[word];
    }
}


static void decode_window_stage(
    PackedBits       local_syndrome[NUM_DETECTOR_WORDS],
    const PackedBits local_carry_in[CARRY_WORDS],
    const Prior      local_priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH],
    PackedBits       local_e_hat[NUM_FAULT_WORDS],
    PackedBits       local_carry_out[CARRY_WORDS],
    PauliFrame*      delta_f_out,
    int*             iterations_used,
    bool*            converged
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    WindowResult result = decode_window(local_syndrome, local_carry_in, local_priors, local_e_hat);

    *delta_f_out = result.delta_f;
    *iterations_used = result.iterations_used;
    *converged = result.converged;

    COPY_CARRY_RESULT:
    for (int word = 0; word < CARRY_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        local_carry_out[word] = result.carry_out[word];
    }
}

void relaybp_top(
    const PackedBits   syndrome_in[NUM_DETECTOR_WORDS],
    const PackedBits   carry_in[CARRY_WORDS],
    const PackedPriors prior_words[NUM_PRIOR_WORDS],
    PackedBits         e_hat_out[NUM_FAULT_WORDS],
    PauliFrame*        delta_f_out,
    PackedBits         carry_out[CARRY_WORDS],
    int*               iterations_used,
    bool*              converged
) {
    // HLS interface configuration
    #pragma HLS INTERFACE m_axi port=syndrome_in offset=slave bundle=gmem_syndrome depth=NUM_DETECTOR_WORDS max_read_burst_length=64 num_read_outstanding=16
    #pragma HLS INTERFACE m_axi port=carry_in    offset=slave bundle=gmem_carry_in depth=CARRY_WORDS        max_read_burst_length=64 num_read_outstanding=16
    #pragma HLS INTERFACE m_axi port=prior_words offset=slave bundle=gmem_priors depth=NUM_PRIOR_WORDS     max_read_burst_length=64 num_read_outstanding=16
    #pragma HLS INTERFACE m_axi port=e_hat_out   offset=slave bundle=gmem_ehat depth=NUM_FAULT_WORDS       max_write_burst_length=64 num_write_outstanding=16
    #pragma HLS INTERFACE m_axi port=carry_out   offset=slave bundle=gmem_carry_out depth=CARRY_WORDS      max_write_burst_length=64 num_write_outstanding=16
    #pragma HLS INTERFACE s_axilite port=delta_f_out
    #pragma HLS INTERFACE s_axilite port=iterations_used
    #pragma HLS INTERFACE s_axilite port=converged
    #pragma HLS INTERFACE s_axilite port=return

    PackedBits local_syndrome[NUM_DETECTOR_WORDS];
    PackedBits local_carry_in[CARRY_WORDS];
    Prior      local_priors[PRIOR_BANK_FACTOR][PRIOR_BANK_DEPTH];
    PackedBits local_e_hat[NUM_FAULT_WORDS];
    PackedBits local_carry_out[CARRY_WORDS];
// clang-format off
    #pragma HLS DATAFLOW
    #pragma HLS BIND_STORAGE variable=local_syndrome  type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=local_syndrome  dim=1 type=cyclic factor=PACKED_BANK_FACTOR
    #pragma HLS ARRAY_PARTITION variable=local_carry_in  dim=1 type=complete
    #pragma HLS ARRAY_PARTITION variable=local_carry_out dim=1 type=complete
    #pragma HLS BIND_STORAGE variable=local_priors    type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=local_priors    dim=1 type=complete
    #pragma HLS BIND_STORAGE variable=local_e_hat     type=ram_2p impl=bram
    #pragma HLS ARRAY_PARTITION variable=local_e_hat     dim=1 type=cyclic factor=PACKED_BANK_FACTOR
    // clang-format on

    load_syndrome_words(syndrome_in, local_syndrome);
    load_carry_words(carry_in, local_carry_in);
    load_priors(prior_words, local_priors);
    decode_window_stage(
        local_syndrome, local_carry_in, local_priors,
        local_e_hat, local_carry_out,
        delta_f_out, iterations_used, converged);
    store_carry_words(local_carry_out, carry_out);
    store_e_hat_words(local_e_hat, e_hat_out);
}
