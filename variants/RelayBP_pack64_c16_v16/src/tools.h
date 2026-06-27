#ifndef TOOLS_H
#define TOOLS_H

#include "constants.h"
#include "types.h"

// MinPair: the data carried at each tree node 
struct MinPair {
    MsgMagnitude    min1;       // smallest value in this subtree
    MsgMagnitude    min2;       // second smallest
    int             min1_idx;   // index where min1 originally came from
};

// make_leaf: Create a single-element MinPair (leaf of the tree)
inline MinPair make_leaf(MsgMagnitude value, int idx) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    MinPair leaf;
    leaf.min1 = value;
    leaf.min2 = MSG_MAX_MAG;
    leaf.min1_idx = idx;
    return leaf;
}

// merge_pairs: Merge two minPair structures into one
inline MinPair merge_pairs(const MinPair& a, const MinPair& b) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    MinPair out;
    
    if (a.min1 <= b.min1) {
        // a'smallest is the overall smallest
        out.min1 = a.min1;
        out.min1_idx = a.min1_idx;
        // 2nd smallest is the smaller of a.min2 and b.min1
        out.min2 = (a.min2 <= b.min1) ? a.min2 : b.min1;
    } else {
        out.min1 = b.min1;
        out.min1_idx = b.min1_idx;
        // 2nd smallest is the smaller of b.min2 and a.min1
        out.min2 = (b.min2 <= a.min1) ? b.min2 : a.min1;
    }
    return out;
}

// TreeReduce<N>: template recursion for building a balanced reduction tree
template<int N>
struct TreeReduce {
    static MinPair apply(const MinPair leaves[N]) {
// clang-format off 
        #pragma HLS INLINE
        // clang-format on
        
        // Split the array into two halves
        constexpr int HALF = N / 2;
        constexpr int REST = N - HALF;

        // Recursively reduce each half
        MinPair left_result = TreeReduce<HALF>::apply(leaves);
        MinPair right_result = TreeReduce<REST>::apply(&leaves[HALF]);

        // Combine the two results
        return merge_pairs(left_result, right_result);
    }
};

// Base case 1: single leaf - already the result
template<>
struct TreeReduce<1> {
    static MinPair apply(const MinPair leaves[1]) {
// clang-format off
        #pragma HLS INLINE
        // clang-format on
        return leaves[0];
        
    }
};

// Base case 2: two leaves - one merge
template<>
struct TreeReduce<2> {
    static MinPair apply(const MinPair leaves[2]) {
// clang-format off
        #pragma HLS INLINE
        // clang-format on
        return merge_pairs(leaves[0], leaves[1]);
    }
};

inline Posterior sat_sub(Posterior a, Posterior b) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    int s = (int)a - (int)b;
    if (s > POST_MAX) return POST_MAX;
    if (s < POST_MIN) return POST_MIN;
    return (Posterior)s;
}

// Saturate plain int back into MsgMagnitude
inline MsgMagnitude sat_mag(int v) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    if (v > MSG_MAX_MAG) return MSG_MAX_MAG;
    if (v < 0) return 0;
    return (MsgMagnitude)v;
}

// Convert sign-magnitude message to signed posterior contribution
// if sign == 1 (negative) return -mag
// else return +mag
inline Posterior msg_to_posterior(const Message &m) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on 
    if (m.sign) return -(Posterior)m.mag;
    return (Posterior)m.mag; 
}

// Convert signed posterior to sign-magnitude message, saturating magnitude
inline Message posterior_to_msg(Posterior p) {
// clang-format off
    #pragma HLS INLINE
    // clang-format on
    Message m;
    if (p < 0) {
        m.sign =1;
        int v = -(int)p;
        m.mag = sat_mag(v);
    } else {
        m.sign = 0;
        m.mag = sat_mag((int)p);
    }
    return m;
}

#endif
