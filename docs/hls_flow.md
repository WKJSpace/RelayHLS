# HLS Flow

Recommended order:

1. Run C simulation.
2. Run HLS C synthesis.
3. Run direct Vivado out-of-context implementation.
4. Collect latency/resource/timing reports from generated outputs.

C simulation must pass before synthesis.

Important generated reports after HLS synthesis:

- `hls/syn/report/csynth.rpt`
- `hls/syn/report/relaybp_top_csynth.rpt`

Important generated reports after OOC implementation:

- `hls/impl/direct_vivado_*/util_synth.rpt`
- `hls/impl/direct_vivado_*/timing_synth.rpt`
- `hls/impl/direct_vivado_*/util_routed.rpt`
- `hls/impl/direct_vivado_*/timing_routed.rpt`
- `hls/impl/direct_vivado_*/route_status.rpt`
