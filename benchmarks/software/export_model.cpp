// Export only the numerical graph and output maps required by the GPU baseline.
// Output remains a private remote file; routing tables and source are not exported.
#include "decoder_top.h"
#include <iostream>
#include <vector>
#include <stdexcept>
#include <type_traits>
#include <cstdint>

template<class T, size_t K> bool commit_bit(const T (&mask)[K], int v) {
    if constexpr (K == NUM_FAULTS) return bool(mask[v]);
    else {
        static_assert(K == NUM_FAULT_WORDS, "Unknown commit-mask layout");
        return (uint64_t(mask[v / PACK_BITS]) >> (v % PACK_BITS)) & 1;
    }
}
static void array(const std::vector<int>& a) {
    std::cout << '[';
    for (size_t i=0; i<a.size(); ++i) { if(i) std::cout << ','; std::cout << a[i]; }
    std::cout << ']';
}
int main() {
    static_assert(NUM_FAULTS==2240 && NUM_DETECTORS==252 && NUM_EDGES==7776);
    static_assert(MSG_INT_BITS==4 && POST_MAG_BITS==7 && WEIGHT_BITS==20);
    static_assert(MAX_LEGS==4 && MAX_ITERS_PER_LEG==10 && GLOBAL_MAX_ITERS==40);
    static_assert(CONVERGENCE_CHECK_INTERVAL==2 && MAX_SOLUTIONS==2 && MEM_SHIFT==3);
    static_assert(PACK_BITS==64 && PRIOR_PACK_FACTOR==64 && K_OBSERVABLES==12 && M_PER_CYCLE==126);
    std::vector<int> faults(NUM_EDGES,-1), used(NUM_EDGES,0);
    for(int c=0;c<NUM_DETECTORS;++c) for(int k=0;k<H_ROW_DEGREES[c];++k) {
        int e=EDGE_FOR_CHECK_POS[c][k],v=H_ROW_NEIGHBORS[c][k];
        if(e<0 || e>=NUM_EDGES || v<0 || v>=NUM_FAULTS || used[e]++) throw std::runtime_error("edge_map");
        faults[e]=v;
    }
    for(int e=0;e<NUM_EDGES;++e) if(used[e]!=1) throw std::runtime_error("edge_missing");
    std::cout << "{\"n\":" << NUM_FAULTS << ",\"m\":" << NUM_DETECTORS << ",\"e\":" << NUM_EDGES
              << ",\"k\":" << K_OBSERVABLES << ",\"carry_count\":" << M_PER_CYCLE
              << ",\"carry_start\":" << CARRY_DETECTOR_START << ",\"policy\":{\"WEIGHT_BITS\":" << WEIGHT_BITS
              << ",\"MEM_SHIFT\":" << MEM_SHIFT << ",\"MAX_LEGS\":" << MAX_LEGS
              << ",\"MAX_ITERS_PER_LEG\":" << MAX_ITERS_PER_LEG << ",\"GLOBAL_MAX_ITERS\":" << GLOBAL_MAX_ITERS
              << ",\"MAX_SOLUTIONS\":" << MAX_SOLUTIONS << ",\"ALPHA_SHIFT_MAX\":" << ALPHA_SHIFT_MAX
              << ",\"CONVERGENCE_CHECK_INTERVAL\":" << CONVERGENCE_CHECK_INTERVAL << ",\"LEG_BETA\":[";
    for(int i=0;i<MAX_LEGS;++i) { if(i)std::cout<<','; std::cout<<LEG_BETA[i]; }
    std::cout << "]},\"row_edges\":[";
    for(int c=0;c<NUM_DETECTORS;++c) { if(c)std::cout<<','; array(std::vector<int>(EDGE_FOR_CHECK_POS[c],EDGE_FOR_CHECK_POS[c]+H_ROW_DEGREES[c])); }
    std::cout << "],\"edge_fault\":";array(faults);
    std::cout << ",\"tail_neighbors\":[";
    for(int l=0;l<K_OBSERVABLES;++l) { if(l)std::cout<<','; array(std::vector<int>(A_ROW_NEIGHBORS[l],A_ROW_NEIGHBORS[l]+A_ROW_DEGREES[l])); }
    for(int i=0;i<M_PER_CYCLE;++i) {
        int c=CARRY_DETECTOR_START+i;
        if(c<0 || c>=NUM_DETECTORS) throw std::runtime_error("carry_range");
        std::cout<<',';array(std::vector<int>(H_ROW_NEIGHBORS[c],H_ROW_NEIGHBORS[c]+H_ROW_DEGREES[c]));
    }
    std::cout << "],\"commit\":[";
    for(int v=0;v<NUM_FAULTS;++v) { if(v)std::cout<<',';std::cout<<int(commit_bit(COMMIT_MASK,v)); }
    std::cout << "]}\n";
}
