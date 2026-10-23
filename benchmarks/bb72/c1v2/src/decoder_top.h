// decoder_top.h — Top-level HLS interface

#ifndef DECODER_TOP_H
#define DECODER_TOP_H

#include "types.h"
#include "constants.h"
#include "windowing.h"

void relaybp_top(
    const PackedBits   syndrome_in[NUM_DETECTOR_WORDS],
    const PackedBits   carry_in[CARRY_WORDS],
    const PackedPriors prior_words[NUM_PRIOR_WORDS],
    PackedBits         e_hat_out[NUM_FAULT_WORDS],
    PauliFrame*        delta_f_out,
    PackedBits         carry_out[CARRY_WORDS],
    int*               iterations_used,
    bool*              converged
);

#endif
