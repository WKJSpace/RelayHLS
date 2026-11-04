#ifndef TYPES_H
#define TYPES_H

#include <cstdint>
#include "constants.h"
#include "ap_int.h"

typedef ap_uint<MSG_INT_BITS>       MsgMagnitude;
typedef ap_uint<1>                  MsgSign;
typedef ap_int<POST_TOTAL_BITS>     Posterior;      // Extra bits for sum overflow
typedef ap_uint<MSG_INT_BITS>       Prior;
typedef ap_uint<1>                  HardDecision;
typedef ap_uint<1>                  Syndrome;
typedef ap_uint<6>                  BetaInt;        // β × MEM_SCALE, ≤ 32 Λ_j(t) = β · Λ_j(0) + (1 - β) · M_j(t-1), To avoid negative
typedef ap_uint<3>                  MemShift;       // log2(MEM_SCALE), ≤ 7
typedef ap_uint<3>                  AlphaShift;     // α = 1 − 2^(−alpha_shift)
typedef ap_uint<WEIGHT_BITS>        WEIGHT;
typedef ap_uint<K_OBSERVABLES>      PauliFrame;
typedef ap_uint<PACK_BITS>          PackedBits;
typedef ap_uint<PRIOR_WORD_BITS>    PackedPriors;
typedef ap_uint<MSG_INT_BITS + 1>   PackedMessage;

// Bundled message: explicit sign + unsigned magnitude
struct Message {
    MsgSign sign;       // 0 = positive  (no error), 1 = negative (error)
    MsgMagnitude mag;   // abs(LLR), quantized
};

inline PackedMessage pack_message(Message msg) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    PackedMessage packed = 0;
    packed[0] = msg.sign;
    packed.range(MSG_INT_BITS, 1) = msg.mag;
    return packed;
}

inline Message unpack_message(PackedMessage packed) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    Message msg;
    msg.sign = packed[0];
    msg.mag = packed.range(MSG_INT_BITS, 1);
    return msg;
}

inline PackedMessage zero_packed_message() {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    return (PackedMessage)0;
}

// Saturation bounds
constexpr int POST_MAX = (1 << POST_MAG_BITS) - 1;
constexpr int POST_MIN = -(1 << POST_MAG_BITS);



#endif
