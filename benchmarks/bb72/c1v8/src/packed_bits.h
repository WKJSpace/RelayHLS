#ifndef PACKED_BITS_H
#define PACKED_BITS_H

#include "types.h"
#include "constants.h"

inline int packed_word_index(int bit_idx) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    return bit_idx / PACK_BITS;
}

inline int packed_bit_offset(int bit_idx) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    return bit_idx % PACK_BITS;
}

inline ap_uint<1> get_packed_bit(
    const PackedBits words[],
    int              bit_idx
) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    int word_idx = packed_word_index(bit_idx);
    int offset = packed_bit_offset(bit_idx);
    return words[word_idx][offset];
}

inline void set_packed_bit(
    PackedBits words[],
    int        bit_idx,
    ap_uint<1> value
) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    int word_idx = packed_word_index(bit_idx);
    int offset = packed_bit_offset(bit_idx);
    words[word_idx][offset] = value;
}

inline void unpack_packed_bits_banked(
    const PackedBits words[],
    HardDecision     banks[PACKED_BANK_FACTOR][PRIOR_BANK_DEPTH]
) {
// clang-format off
    #pragma HLS INLINE off
    // clang-format on
    UNPACK_PACKED_WORDS:
    for (int word = 0; word < NUM_FAULT_WORDS; word++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        PackedBits packed = words[word];

        UNPACK_PACKED_LANES:
        for (int lane = 0; lane < PACK_BITS; lane++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            int j = word * PACK_BITS + lane;
            if (j < NUM_FAULTS) {
                banks[lane][word] = packed[lane];
            }
        }
    }
}

#endif
