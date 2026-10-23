#ifndef BP_ITERATION_H
#define BP_ITERATION_H

#include "types.h"
#include "cnu.h"
#include "vnu.h"
#include "constants.h"
#include "packed_bits.h"
#include <cstdint>
#include <type_traits>
#include <limits>
#include <utility>
#include <cstddef>
#ifndef __SYNTHESIS__
#include <cassert>
#endif

static_assert(EDGE_BANK_PORTS == 2, "cnu_pass/vnu_pass require dual-port message banks");
static_assert((PACK_BITS % VNU_PARALLEL) == 0, "VNU_PARALLEL must divide PACK_BITS");

static_assert(MSG_INT_BITS >= 1 && MSG_INT_BITS < 64,
              "native routing requires a packed payload of 2..64 bits");
using NativeRoutingWord = typename std::conditional<(MSG_INT_BITS + 1 <= 8), std::uint8_t,
    typename std::conditional<(MSG_INT_BITS + 1 <= 16), std::uint16_t,
        typename std::conditional<(MSG_INT_BITS + 1 <= 32), std::uint32_t,
                                  std::uint64_t>::type>::type>::type;
static_assert(std::numeric_limits<NativeRoutingWord>::digits >= MSG_INT_BITS + 1,
              "native routing must preserve every packed payload bit");
inline NativeRoutingWord routing_native_word(const PackedMessage &packed) {
    #pragma HLS INLINE
    return static_cast<NativeRoutingWord>(packed.to_uint64());
}
inline PackedMessage routing_packed_word(NativeRoutingWord word) {
    #pragma HLS INLINE
    return PackedMessage(word);
}

namespace native_packed_route {
constexpr unsigned bits_for_bound(std::uint64_t bound) {
    unsigned bits = 0;
    std::uint64_t maximum = bound - 1;
    do {
        ++bits;
        maximum >>= 1;
    } while (maximum != 0);
    return bits;
}

template<std::uint64_t Parallel, std::uint64_t Degree, std::uint64_t Depth>
struct Layout {
    static_assert(Parallel > 0 && Degree > 0 && Depth > 0,
                  "descriptor dimensions must be positive");
    static constexpr std::uint64_t parallel = Parallel;
    static constexpr std::uint64_t degree = Degree;
    static constexpr std::uint64_t depth = Depth;
    static constexpr unsigned lane_bits = bits_for_bound(Parallel);
    static constexpr unsigned slot_bits = bits_for_bound(Degree);
    static constexpr unsigned addr_bits = bits_for_bound(Depth);
    static constexpr unsigned total_bits = lane_bits + slot_bits + addr_bits;
    static_assert(total_bits <= 64 && addr_bits < 64 && addr_bits + slot_bits < 64,
                  "unsupported descriptor width or shift");
    using Word = typename std::conditional<(total_bits <= 8), std::uint8_t,
        typename std::conditional<(total_bits <= 16), std::uint16_t,
            typename std::conditional<(total_bits <= 32), std::uint32_t,
                                      std::uint64_t>::type>::type>::type;
    static_assert(std::numeric_limits<Word>::digits >= total_bits,
                  "descriptor word is too narrow");
    static constexpr std::uint64_t mask(unsigned width) {
        return ~std::uint64_t(0) >> (64 - width);
    }
    static constexpr std::uint64_t pack(std::uint64_t lane, std::uint64_t slot,
                                        std::uint64_t addr) {
        return addr | (slot << addr_bits) | (lane << (addr_bits + slot_bits));
    }
    static constexpr std::uint64_t lane(std::uint64_t word) {
        return (word >> (addr_bits + slot_bits)) & mask(lane_bits);
    }
    static constexpr std::uint64_t slot(std::uint64_t word) {
        return (word >> addr_bits) & mask(slot_bits);
    }
    static constexpr std::uint64_t addr(std::uint64_t word) {
        return word & mask(addr_bits);
    }
};

struct CnuSource {
    static constexpr int groups = CNU_EDGE_GROUPS;
    static constexpr int banks = EDGE_BANK_FACTOR;
    static constexpr int ports = EDGE_BANK_PORTS;
    static constexpr int valid(std::size_t g, std::size_t b, std::size_t p) {
        return CNU_EDGE_VALID[g][b][p];
    }
    static constexpr int lane(std::size_t g, std::size_t b, std::size_t p) {
        return CNU_EDGE_LANE[g][b][p];
    }
    static constexpr int slot(std::size_t g, std::size_t b, std::size_t p) {
        return CNU_EDGE_SLOT[g][b][p];
    }
    static constexpr int addr(std::size_t g, std::size_t b, std::size_t p) {
        return CNU_EDGE_ADDR[g][b][p];
    }
};
struct VnuSource {
    static constexpr int groups = VNU_EDGE_GROUPS;
    static constexpr int banks = EDGE_BANK_FACTOR;
    static constexpr int ports = EDGE_BANK_PORTS;
    static constexpr int valid(std::size_t g, std::size_t b, std::size_t p) {
        return VNU_EDGE_VALID[g][b][p];
    }
    static constexpr int lane(std::size_t g, std::size_t b, std::size_t p) {
        return VNU_EDGE_LANE[g][b][p];
    }
    static constexpr int slot(std::size_t g, std::size_t b, std::size_t p) {
        return VNU_EDGE_SLOT[g][b][p];
    }
    static constexpr int addr(std::size_t g, std::size_t b, std::size_t p) {
        return VNU_EDGE_ADDR[g][b][p];
    }
};

template<typename LayoutType, typename Source, std::size_t I,
         bool Valid = Source::valid(I / (static_cast<std::size_t>(Source::banks) *
                                         static_cast<std::size_t>(Source::ports)),
                                    (I / static_cast<std::size_t>(Source::ports)) %
                                        static_cast<std::size_t>(Source::banks),
                                    I % static_cast<std::size_t>(Source::ports)) != 0>
struct Entry;

template<typename LayoutType, typename Source, std::size_t I>
struct Entry<LayoutType, Source, I, false> {
    static constexpr typename LayoutType::Word value = 0;
};

template<typename LayoutType, typename Source, std::size_t I>
struct Entry<LayoutType, Source, I, true> {
    static constexpr std::size_t g = I / (static_cast<std::size_t>(Source::banks) *
                                           static_cast<std::size_t>(Source::ports));
    static constexpr std::size_t b = (I / static_cast<std::size_t>(Source::ports)) %
                                     static_cast<std::size_t>(Source::banks);
    static constexpr std::size_t p = I % static_cast<std::size_t>(Source::ports);
    static constexpr int original_lane = Source::lane(g, b, p);
    static constexpr int original_slot = Source::slot(g, b, p);
    static constexpr int original_addr = Source::addr(g, b, p);
    static_assert(original_lane >= 0 &&
                  static_cast<std::uint64_t>(original_lane) < LayoutType::parallel,
                  "valid descriptor lane out of range");
    static_assert(original_slot >= 0 &&
                  static_cast<std::uint64_t>(original_slot) < LayoutType::degree,
                  "valid descriptor slot out of range");
    static_assert(original_addr >= 0 &&
                  static_cast<std::uint64_t>(original_addr) < LayoutType::depth,
                  "valid descriptor address out of range");
    static constexpr std::uint64_t packed = LayoutType::pack(
        static_cast<std::uint64_t>(original_lane),
        static_cast<std::uint64_t>(original_slot),
        static_cast<std::uint64_t>(original_addr));
    static_assert(LayoutType::lane(packed) == static_cast<std::uint64_t>(original_lane) &&
                  LayoutType::slot(packed) == static_cast<std::uint64_t>(original_slot) &&
                  LayoutType::addr(packed) == static_cast<std::uint64_t>(original_addr),
                  "descriptor field roundtrip failed");
    static_assert(LayoutType::lane(packed) <= static_cast<std::uint64_t>(std::numeric_limits<int>::max()) &&
                  LayoutType::slot(packed) <= static_cast<std::uint64_t>(std::numeric_limits<int>::max()) &&
                  LayoutType::addr(packed) <= static_cast<std::uint64_t>(std::numeric_limits<int>::max()),
                  "decoded descriptor field exceeds int");
    static constexpr typename LayoutType::Word value =
        static_cast<typename LayoutType::Word>(packed);
};

template<typename LayoutType, typename Source>
struct Storage {
    using Word = typename LayoutType::Word;
    Word values[Source::groups][Source::banks][Source::ports];
};
template<typename LayoutType, typename Source, std::size_t... I>
constexpr Storage<LayoutType, Source> make_storage(std::index_sequence<I...>) {
    return {{Entry<LayoutType, Source, I>::value...}};
}

template<std::uint64_t Parallel, std::uint64_t Degree>
struct FlatIndexRange {
    static_assert(Parallel > 0 && Degree > 0 &&
                  Parallel <= static_cast<std::uint64_t>(std::numeric_limits<int>::max()) /
                                  (Degree == 0 ? 1 : Degree),
                  "flat scratch index exceeds int");
    static constexpr bool value = true;
};

static_assert(CNU_PARALLEL > 0 && VNU_PARALLEL > 0 &&
              H_MAX_ROW_DEGREE > 0 && H_MAX_COL_DEGREE > 0 &&
              EDGE_BANK_DEPTH > 0 && EDGE_BANK_FACTOR > 0 && EDGE_BANK_PORTS > 0 &&
              CNU_EDGE_GROUPS > 0 && VNU_EDGE_GROUPS > 0,
              "routing dimensions must be positive");
static_assert(FlatIndexRange<CNU_PARALLEL, H_MAX_ROW_DEGREE>::value &&
              FlatIndexRange<VNU_PARALLEL, H_MAX_COL_DEGREE>::value,
              "flat scratch index exceeds int");
static_assert(static_cast<std::size_t>(CNU_EDGE_GROUPS) <=
                  std::numeric_limits<std::size_t>::max() / EDGE_BANK_FACTOR &&
              static_cast<std::size_t>(VNU_EDGE_GROUPS) <=
                  std::numeric_limits<std::size_t>::max() / EDGE_BANK_FACTOR &&
              (static_cast<std::size_t>(CNU_EDGE_GROUPS) * EDGE_BANK_FACTOR) <=
                  std::numeric_limits<std::size_t>::max() / EDGE_BANK_PORTS &&
              (static_cast<std::size_t>(VNU_EDGE_GROUPS) * EDGE_BANK_FACTOR) <=
                  std::numeric_limits<std::size_t>::max() / EDGE_BANK_PORTS,
              "descriptor storage extent exceeds size_t");
using CnuLayout = Layout<CNU_PARALLEL, H_MAX_ROW_DEGREE, EDGE_BANK_DEPTH>;
using VnuLayout = Layout<VNU_PARALLEL, H_MAX_COL_DEGREE, EDGE_BANK_DEPTH>;
using CnuStorage = Storage<CnuLayout, CnuSource>;
using VnuStorage = Storage<VnuLayout, VnuSource>;
static constexpr CnuStorage cnu_storage = make_storage<CnuLayout, CnuSource>(
    std::make_index_sequence<static_cast<std::size_t>(CNU_EDGE_GROUPS) *
                             EDGE_BANK_FACTOR * EDGE_BANK_PORTS>{});
static constexpr VnuStorage vnu_storage = make_storage<VnuLayout, VnuSource>(
    std::make_index_sequence<static_cast<std::size_t>(VNU_EDGE_GROUPS) *
                             EDGE_BANK_FACTOR * EDGE_BANK_PORTS>{});
static_assert(sizeof(cnu_storage.values) ==
              static_cast<std::size_t>(CNU_EDGE_GROUPS) * EDGE_BANK_FACTOR *
              EDGE_BANK_PORTS * sizeof(CnuLayout::Word), "CNU descriptor extent mismatch");
static_assert(sizeof(vnu_storage.values) ==
              static_cast<std::size_t>(VNU_EDGE_GROUPS) * EDGE_BANK_FACTOR *
              EDGE_BANK_PORTS * sizeof(VnuLayout::Word), "VNU descriptor extent mismatch");
} // namespace native_packed_route

#include "cnu_read_index.h"

inline void cnu_pass(
    const PackedMessage v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH],
    const PackedBits syndrome[NUM_DETECTOR_WORDS],
    AlphaShift       alpha_shift,
    PackedMessage    c_to_v[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH]
) {
    const native_packed_route::CnuLayout::Word
        (&cnu_route)[CNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS] =
            native_packed_route::cnu_storage.values;
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS DEPENDENCE variable=v_to_c inter false
    #pragma HLS DEPENDENCE variable=v_to_c intra false
    #pragma HLS DEPENDENCE variable=c_to_v inter false
    #pragma HLS DEPENDENCE variable=c_to_v intra false
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=CNU_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=cnu_route dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=cnu_route dim=3 type=complete
    // clang-format on

    CNU_ROW_GROUPS:
    for (int i_base = 0; i_base < NUM_DETECTORS; i_base += CNU_PARALLEL) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        Message in[CNU_PARALLEL][H_MAX_ROW_DEGREE];
        Message out[CNU_PARALLEL][H_MAX_ROW_DEGREE];
        NativeRoutingWord raw_in[CNU_PARALLEL * H_MAX_ROW_DEGREE];
        NativeRoutingWord raw_out[CNU_PARALLEL * H_MAX_ROW_DEGREE];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=in  dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=in  dim=2 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=2 type=complete
        #pragma HLS ARRAY_PARTITION variable=raw_in dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=raw_out dim=1 type=complete
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
                out[lane][k].sign = 0;
                out[lane][k].mag = 0;
            }
        }

        int group = i_base / CNU_PARALLEL;
        // Fixed bank/port destinations avoid a dynamically addressed write network.
        NativeRoutingWord bank_reads[EDGE_BANK_FACTOR * EDGE_BANK_PORTS];
        #pragma HLS ARRAY_PARTITION variable=bank_reads complete dim=1
        #pragma HLS ARRAY_PARTITION variable=BB72_CNU_READ_INDEX complete dim=2
        #pragma HLS ARRAY_PARTITION variable=BB72_CNU_READ_INDEX complete dim=3
        #pragma HLS ARRAY_PARTITION variable=BB72_CNU_READ_VALID complete dim=2
        #pragma HLS ARRAY_PARTITION variable=BB72_CNU_READ_VALID complete dim=3
        CNU_READ_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
            #pragma HLS UNROLL
            CNU_READ_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
                #pragma HLS UNROLL
                native_packed_route::CnuLayout::Word descriptor = cnu_route[group][bank][port];
                int addr = static_cast<int>(native_packed_route::CnuLayout::addr(descriptor));
                bank_reads[bank * EDGE_BANK_PORTS + port] =
                    CNU_EDGE_VALID[group][bank][port]
                    ? routing_native_word(v_to_c[bank][addr]) : 0;
            }
        }
        // Each lane/slot now has exactly one fixed destination assignment.
        CNU_SELECT_LANES:
        for (int lane = 0; lane < CNU_PARALLEL; lane++) {
            #pragma HLS UNROLL
            CNU_SELECT_SLOTS:
            for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
                #pragma HLS UNROLL
                raw_in[lane * H_MAX_ROW_DEGREE + k] =
                    BB72_CNU_READ_VALID[group][lane][k]
                    ? bank_reads[BB72_CNU_READ_INDEX[group][lane][k]] : 0;
            }
        }

        CNU_UNPACK_LANES:
        for (int lane = 0; lane < CNU_PARALLEL; lane++) {
            #pragma HLS UNROLL
            CNU_UNPACK_SLOTS:
            for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
                #pragma HLS UNROLL
                in[lane][k] = unpack_message(routing_packed_word(raw_in[lane * H_MAX_ROW_DEGREE + k]));
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

        CNU_PACK_LANES:
        for (int lane = 0; lane < CNU_PARALLEL; lane++) {
            #pragma HLS UNROLL
            CNU_PACK_SLOTS:
            for (int k = 0; k < H_MAX_ROW_DEGREE; k++) {
                #pragma HLS UNROLL
                raw_out[lane * H_MAX_ROW_DEGREE + k] = routing_native_word(pack_message(out[lane][k]));
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
                    native_packed_route::CnuLayout::Word descriptor = cnu_route[group][bank][port];
                    int lane = static_cast<int>(native_packed_route::CnuLayout::lane(descriptor));
                    int slot = static_cast<int>(native_packed_route::CnuLayout::slot(descriptor));
                    int addr = static_cast<int>(native_packed_route::CnuLayout::addr(descriptor));
#ifndef __SYNTHESIS__
                    assert(lane >= 0 && lane < CNU_PARALLEL);
                    assert(slot >= 0 && slot < H_MAX_ROW_DEGREE);
                    assert(addr >= 0 && addr < EDGE_BANK_DEPTH);
                    assert(lane == CNU_EDGE_LANE[group][bank][port]);
                    assert(slot == CNU_EDGE_SLOT[group][bank][port]);
                    assert(addr == CNU_EDGE_ADDR[group][bank][port]);
#endif
                    c_to_v[bank][addr] = routing_packed_word(raw_out[lane * H_MAX_ROW_DEGREE + slot]);
                }
            }
        }
    }
}

template<int FirstBank>
inline void vnu_scatter_native_tile(
    int group,
    const NativeRoutingWord raw_out[VNU_PARALLEL * H_MAX_COL_DEGREE],
    PackedMessage v_to_c[EDGE_BANK_FACTOR][EDGE_BANK_DEPTH]
) {
    static_assert(FirstBank >= 0, "first bank must be nonnegative");
    static_assert(FirstBank % 8 == 0, "first bank must align to a tile");
    static_assert(FirstBank + 8 <= EDGE_BANK_FACTOR, "tile exceeds bank factor");
    const native_packed_route::VnuLayout::Word
        (&vnu_route)[VNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS] =
            native_packed_route::vnu_storage.values;
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS PIPELINE II=1
    #pragma HLS DEPENDENCE variable=v_to_c inter false
    #pragma HLS DEPENDENCE variable=v_to_c intra false
    #pragma HLS ARRAY_PARTITION variable=v_to_c dim=1 type=complete
    #pragma HLS ARRAY_PARTITION variable=raw_out dim=1 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=vnu_route dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=vnu_route dim=3 type=complete
    // clang-format on

        VNU_SCATTER_BANKS:
        for (int bank = FirstBank; bank < FirstBank + 8; bank++) {
// clang-format off
            #pragma HLS UNROLL
            // clang-format on
            VNU_SCATTER_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
// clang-format off
                #pragma HLS UNROLL
                // clang-format on
                if (VNU_EDGE_VALID[group][bank][port]) {
                    native_packed_route::VnuLayout::Word descriptor = vnu_route[group][bank][port];
                    int lane = static_cast<int>(native_packed_route::VnuLayout::lane(descriptor));
                    int slot = static_cast<int>(native_packed_route::VnuLayout::slot(descriptor));
                    int addr = static_cast<int>(native_packed_route::VnuLayout::addr(descriptor));
#ifndef __SYNTHESIS__
                    assert(lane >= 0 && lane < VNU_PARALLEL);
                    assert(slot >= 0 && slot < H_MAX_COL_DEGREE);
                    assert(addr >= 0 && addr < EDGE_BANK_DEPTH);
                    assert(lane == VNU_EDGE_LANE[group][bank][port]);
                    assert(slot == VNU_EDGE_SLOT[group][bank][port]);
                    assert(addr == VNU_EDGE_ADDR[group][bank][port]);
#endif
                    v_to_c[bank][addr] = routing_packed_word(raw_out[lane * H_MAX_COL_DEGREE + slot]);
                }
            }
        }

}

#include "vnu_read_index.h"

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
    const native_packed_route::VnuLayout::Word
        (&vnu_route)[VNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS] =
            native_packed_route::vnu_storage.values;
// clang-format off
    #pragma HLS INLINE off
    #pragma HLS DEPENDENCE variable=c_to_v inter false
    #pragma HLS DEPENDENCE variable=c_to_v intra false
    #pragma HLS DEPENDENCE variable=v_to_c inter false
    #pragma HLS DEPENDENCE variable=v_to_c intra false
    #pragma HLS ARRAY_PARTITION variable=c_to_v dim=1 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=VNU_EDGE_VALID dim=3 type=complete
    #pragma HLS ARRAY_PARTITION variable=vnu_route dim=2 type=complete
    #pragma HLS ARRAY_PARTITION variable=vnu_route dim=3 type=complete
    // clang-format on

    // Flattened single-pipeline VNU: one continuous II=1 pipeline over all
    // VNU_EDGE_GROUPS groups.  Each group  processes VNU_PARALLEL lanes and 
    // issues at most EDGE_BANK_PORTS accesses per banks.
    constexpr int GROUPS_PER_WORD = PACK_BITS / VNU_PARALLEL;

    ap_uint<PACK_BITS> hd_word_acc = 0;

    VNU_GROUPS:
    for (int group = 0; group < VNU_EDGE_GROUPS; group++) {
// clang-format off
        #pragma HLS PIPELINE II=1
        // clang-format on
        Message in[VNU_PARALLEL][H_MAX_COL_DEGREE];
        Message out[VNU_PARALLEL][H_MAX_COL_DEGREE];
        NativeRoutingWord raw_in[VNU_PARALLEL * H_MAX_COL_DEGREE];
        NativeRoutingWord raw_out[VNU_PARALLEL * H_MAX_COL_DEGREE];
// clang-format off
        #pragma HLS ARRAY_PARTITION variable=in  dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=in  dim=2 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=out dim=2 type=complete
        #pragma HLS ARRAY_PARTITION variable=raw_in dim=1 type=complete
        #pragma HLS ARRAY_PARTITION variable=raw_out dim=1 type=complete
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
                out[lane][k].sign = 0;
                out[lane][k].mag = 0;
            }
        }

        // Fixed bank/port destinations avoid a dynamically addressed write network.
        NativeRoutingWord bank_reads[EDGE_BANK_FACTOR * EDGE_BANK_PORTS];
        #pragma HLS ARRAY_PARTITION variable=bank_reads complete dim=1
        #pragma HLS ARRAY_PARTITION variable=BB72_VNU_READ_INDEX complete dim=2
        #pragma HLS ARRAY_PARTITION variable=BB72_VNU_READ_INDEX complete dim=3
        #pragma HLS ARRAY_PARTITION variable=BB72_VNU_READ_VALID complete dim=2
        #pragma HLS ARRAY_PARTITION variable=BB72_VNU_READ_VALID complete dim=3
        VNU_READ_BANKS:
        for (int bank = 0; bank < EDGE_BANK_FACTOR; bank++) {
            #pragma HLS UNROLL
            VNU_READ_PORTS:
            for (int port = 0; port < EDGE_BANK_PORTS; port++) {
                #pragma HLS UNROLL
                native_packed_route::VnuLayout::Word descriptor = vnu_route[group][bank][port];
                int addr = static_cast<int>(native_packed_route::VnuLayout::addr(descriptor));
                bank_reads[bank * EDGE_BANK_PORTS + port] =
                    VNU_EDGE_VALID[group][bank][port]
                    ? routing_native_word(c_to_v[bank][addr]) : 0;
            }
        }
        // Each lane/slot now has exactly one fixed destination assignment.
        VNU_SELECT_LANES:
        for (int lane = 0; lane < VNU_PARALLEL; lane++) {
            #pragma HLS UNROLL
            VNU_SELECT_SLOTS:
            for (int k = 0; k < H_MAX_COL_DEGREE; k++) {
                #pragma HLS UNROLL
                raw_in[lane * H_MAX_COL_DEGREE + k] =
                    BB72_VNU_READ_VALID[group][lane][k]
                    ? bank_reads[BB72_VNU_READ_INDEX[group][lane][k]] : 0;
            }
        }

        VNU_UNPACK_LANES:
        for (int lane = 0; lane < VNU_PARALLEL; lane++) {
            #pragma HLS UNROLL
            VNU_UNPACK_SLOTS:
            for (int k = 0; k < H_MAX_COL_DEGREE; k++) {
                #pragma HLS UNROLL
                in[lane][k] = unpack_message(routing_packed_word(raw_in[lane * H_MAX_COL_DEGREE + k]));
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

        VNU_PACK_LANES:
        for (int lane = 0; lane < VNU_PARALLEL; lane++) {
            #pragma HLS UNROLL
            VNU_PACK_SLOTS:
            for (int k = 0; k < H_MAX_COL_DEGREE; k++) {
                #pragma HLS UNROLL
                raw_out[lane * H_MAX_COL_DEGREE + k] = routing_native_word(pack_message(out[lane][k]));
            }
        }

        vnu_scatter_native_tile<0>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<8>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<16>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<24>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<32>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<40>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<48>(group, raw_out, v_to_c);
        vnu_scatter_native_tile<56>(group, raw_out, v_to_c);

        // Assemble packed hard-decision words: GROUPS_PER_WORD consecutive
        // groups fill one PACK_BITS word.  Each group writes a disjoint
        // VNU_PARALLEL-bit slice of a carried accumulator, so there is no
        // read-modify-write hazard and the pipeline holds II=1.
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
