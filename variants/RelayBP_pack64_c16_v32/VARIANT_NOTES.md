# RelayBP Wide Priors Pack64 CNU16 VNU32

Role:

```text
Synthetic nonzero H~ matrix variant for HLS performance/resource testing.
The nonzero matrix prevents HLS from deleting CNU/VNU edge-message logic.
VNU parallelism is limited to 32 so one lane group generates at most two
writes to each dual-port edge-memory bank.
```

Parameter settings:

```cpp
PACK_BITS = 64
PACKED_BANK_FACTOR = 64
CNU_PARALLEL = 16
VNU_PARALLEL = 32
CONVERGENCE_PARALLEL = 16
H_ROW_DEGREE = 8  // synthetic, every row
NUM_EDGES = 27648
```

Fake H~ generation:

```text
tools/generate_fake_h_constants.py
```

Generated matrix summary:

```text
NUM_DETECTORS = 3456
NUM_FAULTS = 20000
NUM_EDGES = 27648
row degree min/max = 8/8
column degree min/max = 1/3
active columns = 20000
```

Clock setting:

```text
10 ns from hls_config.cfg
```
