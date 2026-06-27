# testbench

C simulation assets for validating `relaybp_top` before synthesis.

- `relaybp_tb.cpp`: deterministic C simulation testbench.
- `csim_config.tcl`: standalone Tcl-based C simulation helper.

Preferred GitHub-project flow is to use the root-level Vitis command:

```bash
../../scripts/run_csim_all.sh
```

That command uses each variant's `hls_config.cfg`, so Vitis records the simulation status on the main component.
