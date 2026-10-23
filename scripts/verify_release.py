#!/usr/bin/env python3
"""Verify released files, fixture layouts, evidence bindings and derived metrics.

This offline command never invokes a compiler, vendor tool, network or decoder.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def require(condition, message):
    if not condition:raise ValueError(message)

def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_selection(scope):
    require(set(scope['BB72'])=={f'C{c}V{v}' for c in [1,2,4] for v in [2,4,8]} and len(scope['BB72'])==9,'BB72 selection')
    require(scope['BB144']==['C4V8'],'BB144 selection must be C4V8 only')

def service_rate(total, count, clock):
    require(count==31,'Expected 31 service intervals')
    require(total>0 and clock>0,'Invalid timing')
    return count*clock*1_000_000/total

def verify_fixture(folder):
    config=load(folder/'config.json')
    detectors=config['WINDOW_W']*config['M_PER_CYCLE'];faults=config['NUM_FAULTS']
    values=list(map(int,(folder/'inputs.txt').read_text().split()))
    require(len(values)==1+faults+32*detectors and values[0]==32,'Invalid input layout')
    require(all(0<=p<2**config['MSG_INT_BITS'] for p in values[1:1+faults]),'Invalid prior range')
    require(all(b in [0,1] for b in values[1+faults:]),'Invalid syndrome bit')
    golden=(folder/'golden.txt').read_text().splitlines()
    require(len(golden)==32,'Expected 32 golden cases')
    for row in golden:
        parts=row.split();require(len(parts)==6,'Invalid golden fields')
        require([len(v) for v in parts[3:]]==[faults,config['LOGICAL_QUBITS'],config['M_PER_CYCLE']],'Invalid golden width')
        require(all(re.fullmatch('[01]+',v) for v in parts[3:]),'Invalid golden bits')
        iterations,candidates,converged=map(int,parts[:3])
        require(0<=iterations<=config['GLOBAL_MAX_ITERS'] and 0<=candidates<=config['MAX_SOLUTIONS'] and converged in [0,1],'Invalid golden controller fields')
    return {'cases':len(golden),'detectors':detectors,'stored_faults':faults}

def close(actual,expected,label):
    require(math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-8),label)

def verify_workbook(path):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        # The released workbook preserves its original sheet order.
        tree=ET.fromstring(z.read('xl/worksheets/sheet10.xml'))
        points=[]
        for c in tree.findall('.//s:c',ns):
            val=c.find('s:v',ns);inline=c.find('s:is',ns)
            text=val.text if val is not None else ''.join(inline.itertext()) if inline is not None else ''
            if c.get('t')=='s':text=strings[int(text)]
            if re.fullmatch(r'C\d+V\d+',text or ''):points.append(text)
            require(c.get('t')!='e','Workbook error in BB144 sheet')
        require(set(points)=={'C4V8'},'Workbook BB144 selection')

def verify(root=ROOT):
    manifest=load(root/'release_manifest.json');verify_selection(manifest['scope'])
    data=load(root/'data/evaluation.json');verify_selection(data['release_scope'])
    require(len(manifest['configuration_snapshots'])==10,'Expected ten source snapshots')
    expected_dirs={f'{w.lower()}/{point.lower()}' for w,points in manifest['scope'].items() for point in points}
    actual_dirs={str(p.parent.relative_to(root/'benchmarks')) for p in (root/'benchmarks').glob('bb*/*/config.json')}
    require(actual_dirs==expected_dirs,'Unexpected benchmark configuration')
    for snapshot in manifest['configuration_snapshots']:
        key=f"{snapshot['workload'].lower()}/{snapshot['point'].lower()}"
        folder=root/'benchmarks'/key
        fixture=verify_fixture(folder)
        for name,pins in snapshot['files'].items():
            require(sha(root/name)==pins['release_sha256'],'Release source hash mismatch: '+name)
            if '/src/' in name:require(pins['release_sha256']==pins['validated_sha256'],'Synthesis source changed: '+name)
        evidence=load(root/'data'/snapshot['workload'].lower()/'validation'/(snapshot['point'].lower()+'.json'))
        hls=evidence['HLS'];route=evidence['RTL_and_route']
        require(hls['actual_vendor_exit']==0 and hls['ordered_Csim32_exact'],'HLS completion evidence')
        require(hls['HLS_final_sha256']==route['hls_final_sha256'] and hls['native_final_sha256']==route['native_final_sha256'],'Native/HLS/RTL binding mismatch')
        require(all(hls['all7requires'].values()),'HLS preservation/cleanup gate')
        require(route['validation_passed'] and route['both_actual_vendor_exits_zero_and_cleanup_complete'],'RTL/route completion gate')
        require(route['RTL_gate']['comparisons']==160,'Expected 160 output comparisons')
        schedules=hls['complete_group_schedules']
        require({r['loop'] for r in schedules}=={'CNU_ROW_GROUPS','VNU_GROUPS'},'Missing complete-group schedules')
        for r in schedules:
            divisor=snapshot['C'] if r['loop']=='CNU_ROW_GROUPS' else snapshot['V']
            total=fixture['detectors'] if r['loop']=='CNU_ROW_GROUPS' else fixture['stored_faults']
            require(r['achieved_II']==1 and r['trip_count']==math.ceil(total/divisor),'Complete-group II/trip count')
        require(route['route']['fully_routed_nets']==route['route']['routable_nets'],'Unrouted nets')
        require(all(v>=0 for v in route['route']['timing_slacks_ns'].values()),'Timing failure')
        rows=data['BB72_results'] if snapshot['workload']=='BB72' else data['BB144_evaluation']['rows']
        result=next(r for r in rows if r['point']==snapshot['point'])
        require(result['controller_final_sha256']==route['controller_final_sha256'],'Result/controller binding')
        latency=route['latency_cycles'];service=route['service_cycles']
        require(latency['count']==32 and service['count']==31,'Incomplete timing cases')
        close(result['latency_mean_us'],latency['sum']/32/100,'Latency calculation')
        rate=service_rate(service['sum'],31,100)
        close(result.get('throughput_frames_s',result.get('throughput_decodings_s')),rate,'Service rate calculation')
        close(result.get('energy_efficiency_frames_J_est',result.get('energy_efficiency_decodings_J_est')),rate/result['power_total_W_est'],'Estimated energy calculation')
    with (root/'data/RTL_per_case_timing.csv').open(newline='') as f:timings=list(csv.DictReader(f))
    require(len(timings)==320,'Expected 320 per-case latencies')
    for snapshot in manifest['configuration_snapshots']:
        rows=[r for r in timings if r['workload']==snapshot['workload'] and r['point']==snapshot['point']]
        require([int(r['case_index']) for r in rows]==list(range(32)),'Timing case order')
        evidence=load(root/'data'/snapshot['workload'].lower()/'validation'/(snapshot['point'].lower()+'.json'))['RTL_and_route']
        require(sum(int(r['latency_cycles']) for r in rows)==evidence['latency_cycles']['sum'],'Per-case latency sum')
        require(rows[-1]['service_interval_cycles']=='' and sum(int(r['service_interval_cycles']) for r in rows[:-1])==evidence['service_cycles']['sum'],'Per-case service sum')
        require(all(r['source_trace_sha256']==evidence['RTL_gate']['trace_sha256'] for r in rows),'Timing trace binding')
    for name in ['bb72/matrix.csv','bb72/resource_utilization.csv','bb144/matrix.csv']:
        with (root/'data'/name).open(newline='') as f:
            for row in csv.DictReader(f):
                for header,value in row.items():
                    if '(%)' in header:require(0<=float(value)<=100 and '%' not in value,'Resource percentage format')
    verify_workbook(root/'data/RelayHLS_Evaluation.xlsx')
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);p=Path(name)
        require(not p.is_absolute() and '..' not in p.parts,'Unsafe checksum path')
        require(sha(root/p)==digest,'File checksum mismatch: '+name)
    return {'source_snapshots':10,'BB72_points':9,'BB144_points':['C4V8'],'native_golden_cases':320,'RTL_output_comparisons':1600,'latencies':320,'service_intervals':310,'offline_checks':'passed'}

if __name__=='__main__':
    try:print(json.dumps(verify(),indent=2))
    except (ValueError,OSError,KeyError) as error:
        print('Release verification failed: '+str(error),file=sys.stderr);sys.exit(1)
