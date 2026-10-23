// Serial-shot full-top CPU timing. Input preparation and checks are outside timers.
#define main original_cpu_baseline_main
#include "cpu_baseline.cpp"
#undef main
#include "decoder_top.h"
#include <array>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <sched.h>

constexpr int EBYTES=NUM_FAULT_WORDS*PACK_BITS/8;
constexpr int SBYTES=NUM_DETECTOR_WORDS*PACK_BITS/8;
constexpr int PBYTES=NUM_PRIOR_WORDS*PRIOR_PACK_FACTOR*MSG_INT_BITS/8;
constexpr int FBYTES=(K_OBSERVABLES+7)/8;
constexpr int CBYTES=CARRY_WORDS*PACK_BITS/8;
struct Inputs { std::array<uint8_t,SBYTES> syndrome{};std::array<uint8_t,PBYTES> prior{};std::array<uint8_t,CBYTES> carry{}; };
struct Outputs { std::array<uint8_t,EBYTES> estimate{};std::array<uint8_t,FBYTES> frame{};std::array<uint8_t,CBYTES> carry{};int iterations=0;bool converged=false; };
struct Expected { int iterations,solutions;bool converged;std::string estimate,frame,carry; };
template<class T,size_t K> bool commit_bit(const T(&mask)[K],int v) {
 if constexpr(K==NUM_FAULTS) return bool(mask[v]);
 else {static_assert(K==NUM_FAULT_WORDS);return (uint64_t(mask[v/PACK_BITS])>>(v%PACK_BITS))&1;}
}
static int bit(const uint8_t* p,int i) { return (p[i/8]>>(i%8))&1; }
static void set(uint8_t* p,int i,bool b) { if(b)p[i/8]|=uint8_t(1u<<(i%8)); }

struct FullCPU {
 Workspace work;
 std::vector<int> prior=std::vector<int>(NUM_FAULTS);
 std::vector<uint8_t> syndrome=std::vector<uint8_t>(NUM_DETECTORS);
 std::vector<uint8_t> committed=std::vector<uint8_t>(NUM_FAULTS);
 Outputs out;
 PackedBits hsy[NUM_DETECTOR_WORDS],hci[CARRY_WORDS],he[NUM_FAULT_WORDS],hco[CARRY_WORDS];
 PackedPriors hp[NUM_PRIOR_WORDS];PauliFrame hf;int hi=0;bool hc=false;
 int last_solutions=0;
 void prepare_hls_input(const Inputs& in) {
  for(int w=0;w<NUM_DETECTOR_WORDS;++w){hsy[w]=0;for(int k=0;k<PACK_BITS;++k)hsy[w][k]=bit(in.syndrome.data(),w*PACK_BITS+k);}
  for(int w=0;w<CARRY_WORDS;++w){hci[w]=0;for(int k=0;k<PACK_BITS;++k)hci[w][k]=bit(in.carry.data(),w*PACK_BITS+k);}
  for(int w=0;w<NUM_PRIOR_WORDS;++w){hp[w]=0;for(int k=0;k<PRIOR_PACK_FACTOR*MSG_INT_BITS;++k)hp[w][k]=bit(in.prior.data(),w*PRIOR_PACK_FACTOR*MSG_INT_BITS+k);}
 }
 void hls_call() { relaybp_top(hsy,hci,hp,he,&hf,hco,&hi,&hc); }
 void hls_output() {
  out=Outputs{};out.iterations=hi;out.converged=hc;
  for(int v=0;v<NUM_FAULTS;++v)set(out.estimate.data(),v,bool(he[v/PACK_BITS][v%PACK_BITS]));
  for(int l=0;l<K_OBSERVABLES;++l)set(out.frame.data(),l,bool(hf[l]));
  for(int i=0;i<M_PER_CYCLE;++i)set(out.carry.data(),i,bool(hco[i/PACK_BITS][i%PACK_BITS]));
 }
 void optimized_call(const Inputs& in,int threads) {
  // Packed-input decoding is part of the timed function, as in the FPGA top.
  for(int v=0;v<NUM_FAULTS;++v)prior[v]=(in.prior[v/2]>>((v%2)*MSG_INT_BITS))&MSG_MAX_MAG;
  for(int c=0;c<NUM_DETECTORS;++c)syndrome[c]=bit(in.syndrome.data(),c)^(c<M_PER_CYCLE ? bit(in.carry.data(),c):0);
  out=Outputs{};int updates=0,solutions=0;
  out.converged=decode(prior,syndrome,work,threads,updates,solutions);
  out.iterations=updates;last_solutions=solutions;
  for(int v=0;v<NUM_FAULTS;++v) {set(out.estimate.data(),v,work.best[v]);committed[v]=work.best[v]&&commit_bit(COMMIT_MASK,v);}
  for(int l=0;l<K_OBSERVABLES;++l) {
   unsigned parity=0;
   for(int k=0;k<A_ROW_DEGREES[l];++k)parity^=committed[A_ROW_NEIGHBORS[l][k]];
   set(out.frame.data(),l,parity);
  }
  for(int i=0;i<M_PER_CYCLE;++i) {
   int c=CARRY_DETECTOR_START+i;unsigned parity=0;
   for(int k=0;k<H_ROW_DEGREES[c];++k)parity^=committed[H_ROW_NEIGHBORS[c][k]];
   set(out.carry.data(),i,parity);
  }
 }
 void validate(const Expected& e,bool is_hls) {
  if(out.iterations!=e.iterations || out.converged!=e.converged)throw std::runtime_error("control_mismatch");
  if(!is_hls && last_solutions!=e.solutions)throw std::runtime_error("candidate_count_mismatch");
  for(int v=0;v<NUM_FAULTS;++v)if(bit(out.estimate.data(),v)!=(e.estimate[v]=='1'))throw std::runtime_error("estimate_mismatch");
  for(int l=0;l<K_OBSERVABLES;++l)if(bit(out.frame.data(),l)!=(e.frame[l]=='1'))throw std::runtime_error("frame_mismatch");
  for(int i=0;i<M_PER_CYCLE;++i)if(bit(out.carry.data(),i)!=(e.carry[i]=='1'))throw std::runtime_error("carry_mismatch");
 }
};
int main(int argc,char**argv) {
 try {
  if(argc!=6)throw std::runtime_error("arguments");
  bool hls=std::string(argv[1])=="hls";int threads=std::stoi(argv[2]);if(threads<1||threads>8)throw std::runtime_error("threads");
  omp_set_dynamic(0);omp_set_num_threads(threads);
  int actual_team=0;
  #pragma omp parallel num_threads(threads)
  {
   #pragma omp single
   actual_team=omp_get_num_threads();
  }
  if(actual_team!=threads)throw std::runtime_error("OpenMP_team_size");
  std::ifstream input(argv[3]),golden(argv[4]);int count=0;input>>count;if(count!=32)throw std::runtime_error("32_inputs");
  Inputs common;
  for(int v=0;v<NUM_FAULTS;++v){int p;input>>p;if(p<0||p>15)throw std::runtime_error("prior");common.prior[v/2]|=uint8_t(p<<((v%2)*4));}
  std::array<Inputs,32> inputs;std::array<Expected,32> expected;
  for(int i=0;i<32;++i){inputs[i]=common;for(int c=0;c<NUM_DETECTORS;++c){int b;input>>b;if(b!=0&&b!=1)throw std::runtime_error("syndrome");set(inputs[i].syndrome.data(),c,b);}int conv;auto&e=expected[i];golden>>e.iterations>>e.solutions>>conv>>e.estimate>>e.frame>>e.carry;e.converged=conv;if(e.estimate.size()!=NUM_FAULTS||e.frame.size()!=K_OBSERVABLES||e.carry.size()!=M_PER_CYCLE)throw std::runtime_error("golden_width");}
  std::string extra;if(!input||!golden||(input>>extra)||(golden>>extra))throw std::runtime_error("input_layout");
  FullCPU cpu;
  auto call=[&](int i){if(hls){cpu.prepare_hls_input(inputs[i]);cpu.hls_call();cpu.hls_output();}else cpu.optimized_call(inputs[i],threads);cpu.validate(expected[i],hls);};
  for(int i=0;i<32;++i)call(i); // Required independent exact full-top gate before timings.
  for(int i=0;i<8;++i)call(i);
  std::array<std::array<double,32>,5> elapsed;
  for(int trial=0;trial<5;++trial)for(int i=0;i<32;++i){
   if(hls)cpu.prepare_hls_input(inputs[i]);
   auto start=std::chrono::steady_clock::now();
   if(hls)cpu.hls_call();else cpu.optimized_call(inputs[i],threads);
   auto end=std::chrono::steady_clock::now();
   elapsed[trial][i]=std::chrono::duration<double,std::micro>(end-start).count();
   if(hls)cpu.hls_output();cpu.validate(expected[i],hls);
  }
  std::ofstream report(argv[5]);report<<std::setprecision(12)<<"{\"full_top_cases\":32,\"field_comparisons\":160,\"output_mismatches\":0,\"batch_size\":1,\"threads\":"<<threads<<",\"actual_omp_team_size\":"<<actual_team<<",\"hls_c\":"<<(hls?"true":"false")<<",\"timed_trials\":[";
  for(int t=0;t<5;++t){if(t)report<<',';report<<'[';for(int i=0;i<32;++i){if(i)report<<',';report<<elapsed[t][i];}report<<']';}report<<"]}\n";
  return report?0:2;
 } catch(const std::exception&e){std::cerr<<"CPU benchmark failed: "<<e.what()<<'\n';return 1;}
}
