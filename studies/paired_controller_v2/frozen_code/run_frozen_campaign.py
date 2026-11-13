"""Accepted synthetic v2 campaign. Freeze protocol, save every case, never tune."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import yaml

import corrected_rectangular_pilot as base
from independent_controller_check import HERE,REPO,read_parameters

ROOT=HERE/'campaign_v2'
CONTROLLERS=['pure_pursuit','lqr','mpc']
CELLS=[{'name':'nominal','mu_factor':1.,'mass_I_factor':1.,'added_delay_ms':0},
       {'name':'mu_0p8','mu_factor':.8,'mass_I_factor':1.,'added_delay_ms':0},
       {'name':'mu_1p2','mu_factor':1.2,'mass_I_factor':1.,'added_delay_ms':0},
       {'name':'mass_I_0p9','mu_factor':1.,'mass_I_factor':.9,'added_delay_ms':0},
       {'name':'mass_I_1p1','mu_factor':1.,'mass_I_factor':1.1,'added_delay_ms':0},
       {'name':'delay_10ms','mu_factor':1.,'mass_I_factor':1.,'added_delay_ms':10},
       {'name':'delay_30ms','mu_factor':1.,'mass_I_factor':1.,'added_delay_ms':30}]


def atomic_json(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)


def scenarios():
    rows=[]
    for seed in range(883200,883220):
        rng=np.random.default_rng(seed)
        rows.append({'seed':seed,'initial_lateral_error_m':float(rng.uniform(-.1,.1)),
                     'initial_heading_error_rad':float(rng.uniform(-2.,2.)*np.pi/180),
                     'speed_profile_multiplier':float(rng.uniform(.95,1.05))})
    return rows


def freeze_protocol():
    ROOT.mkdir(exist_ok=True)
    p=base.protocol()
    p['version']='racing-v2-paired-campaign-20261113'
    p['authorization']='Parent explicitly approved20paired scenarios/controller nominal plus6prespecified OATcells after the three rectangular-footprint sanity pilots.'
    p['campaign_not_launched']=None
    p['scenario_draws']=scenarios();p['cells']=CELLS
    p['case_count']=len(CONTROLLERS)*len(p['scenario_draws'])*len(CELLS)
    p['controller_tuning']='No controller retuning. Frozen rectangular pilot laws,Q,R,horizon,trim,grid and constraints.'
    p['pairing']='Each cell uses identical20scenario draws; same realization across controllers. Controller order per seed/cell is a deterministic PCG64 permutation.'
    p['uncertainty']='Paired differences and paired bootstrap intervals over scenario seeds. Completion proportions include failures; lap-time intervals are conditional on common completions and report that denominator.'
    p['mass_limitation']='m and yawI scale together. In this normalized-tire model m/I stays fixed and mass cancels elsewhere; expected structural null, not physical mass-robustness evidence.'
    p['physical_domain']='Perfect state; normalized linear-tire F110 dynamics; no battery, sensor, tire saturation or real-car validation. Record slip and lateral-acceleration/mu*g proxies. Exceedance is a model-validity warning, not silently excluded data.'
    p['timing_scope']='Full controller-call wall times on a shared Windows host. Other CPU work may run concurrently. No hard-real-time hardware claim.'
    p['local_integration_gate']={'steps_s':[.004,.002,.001],'scenario':'Independent fixed-control RK4 source-plant straight-to-turn transient2s at3m/s, steer .05rad, rate .03rad/s, accel .3m/s2.',
                                  'max_abs_last_refinement_state_change_limit':1e-4,
                                  'scope':'Local source-integrator sanity; not a whole-trajectory global error bound.'}
    p['source_hashes']={str(path.relative_to(HERE)):hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in [HERE/'corrected_pilot.py',HERE/'corrected_rectangular_pilot.py',Path(__file__),HERE/'independent_controller_check.py']}
    frozen=ROOT/'PROTOCOL.json'
    if frozen.exists() and json.loads(frozen.read_text())!=p:raise RuntimeError('Existing frozen protocol differs; no overwrite')
    atomic_json(frozen,p)
    return p


def integration_preflight(p):
    states=[]
    for dt in [.004,.002,.001]:
        state=np.array([0.,0.,.05,3.,0.,0.,0.]);u=np.array([.03,.3])
        for _ in range(round(2/dt)):
            k1=base.derivative(state,u,p);k2=base.derivative(state+dt*k1/2,u,p)
            k3=base.derivative(state+dt*k2/2,u,p);k4=base.derivative(state+dt*k3,u,p)
            state+=dt*(k1+2*k2+2*k3+k4)/6
        states.append(state)
    error=float(max(abs(states[-1]-states[-2])))
    result={'steps_s':[.004,.002,.001],'states':[s.tolist() for s in states],
            'last_step_max_absolute_change':error,'limit':1e-4,'passed':error<=1e-4}
    atomic_json(ROOT/'integration_preflight.json',result)
    if not result['passed']:raise RuntimeError('Source integration preflight failed')


def run_case(name,nominal,physical,conf,w,geom,clearance,mc,scenario,cell):
    folder=ROOT/'cases'/cell['name']/str(scenario['seed'])/name
    folder.mkdir(parents=True,exist_ok=True)
    result_path=folder/'result.json'
    if result_path.exists():raise RuntimeError('Case exists; do not silently rerun')
    planner=base.Planner(conf,nominal['lf']+nominal['lr'])
    controller=base.RateController(name,nominal,planner,base.ModelCache(nominal),speed_scale=1.2*scenario['speed_profile_multiplier'])
    heading=geom.at(w[0,1:3])['heading'];normal=np.array([-math.sin(heading),math.cos(heading)])
    pos=w[0,1:3]+scenario['initial_lateral_error_m']*normal
    x=np.array([pos[0],pos[1],0.,0.,heading+scenario['initial_heading_error_rad'],0.,0.])
    prev=geom.at(x[:2])['progress'];progress=0.;u=np.zeros(2)
    delay=.004+cell['added_delay_ms']/1000
    queue=deque([u.copy() for _ in range(round(delay/base.DT))])
    trace=[];wall=time.perf_counter();reason='timeout'
    for i in range(round(base.MAX_TIME/base.DT)):
        info=geom.at(x[:2])
        if i%base.HOLD==0:u=controller.command(x,info)
        queue.append(u.copy());applied=queue.popleft()
        if abs(applied[0])>nominal['sv_max']+1e-8 or abs(applied[1])>nominal['a_max']+1e-8:
            raise RuntimeError('Physical input bound failed')
        x=base.step(x,applied,physical)
        if not np.all(np.isfinite(x)):raise RuntimeError('Nonfinite plant state')
        if abs(x[2])>nominal['s_max']+nominal['sv_max']*base.DT+1e-8:raise RuntimeError('Steering state bound failed')
        if x[3]>nominal['v_max']+nominal['a_max']*base.DT+1e-8 or x[3]<nominal['v_min']-nominal['a_max']*base.DT-1e-8:
            raise RuntimeError('Speed state bound failed')
        ni=geom.at(x[:2]);ds=ni['progress']-prev
        if ds < -geom.length/2:ds+=geom.length
        elif ds>geom.length/2:ds-=geom.length
        progress+=ds;prev=ni['progress']
        col=int((x[0]-mc['origin'][0])/mc['resolution']);row=int((x[1]-mc['origin'][1])/mc['resolution'])
        gap=clearance[row,col] if 0<=row<clearance.shape[0] and 0<=col<clearance.shape[1] else 0.
        trace.append([base.DT*(i+1),*x,*applied,ni['ey'],progress,gap])
        if base.rectangular_contact(x,mc):reason='rectangular_map_contact';break
        if progress>=geom.length:reason='one_circuit';break
    arr=np.array(trace);times=np.array(controller.timings)
    np.savetxt(folder/'trace.csv',arr,delimiter=',',header='time_s,x_m,y_m,steer_rad,v_mps,yaw_rad,yaw_rate_radps,beta_rad,applied_steer_rate_radps,applied_acceleration_mps2,cte_m,unwrapped_progress_m,obstacle_center_distance_m',comments='')
    np.savetxt(folder/'controller_times_s.csv',times,delimiter=',',header='full_controller_call_seconds',comments='')
    accel_proxy=np.abs(arr[:,4]*arr[:,6])/(physical['mu']*9.81)
    result={'cell':cell['name'],'scenario':scenario,'controller':name,'reason':reason,'completed_one_circuit':reason=='one_circuit',
            'time_s':float(arr[-1,0]),'progress_m':float(progress),'rms_cte_m':float(np.sqrt(np.mean(arr[:,10]**2))),
            'max_abs_cte_m':float(max(abs(arr[:,10]))),'wall_seconds':time.perf_counter()-wall,
            'control_calls':len(times),'full_call_p50_ms':float(np.quantile(times,.5)*1000),
            'full_call_p95_ms':float(np.quantile(times,.95)*1000),'full_call_max_ms':float(max(times)*1000),
            'calls_over_10ms':int(np.sum(times>.01)),'common_PP_startup_calls':controller.startup_count,
            'mpc_successful_solves':len(controller.flags),'max_abs_beta_rad':float(max(abs(arr[:,7]))),
            'max_lateral_accel_over_mu_g_proxy':float(max(accel_proxy)),
            'physics_steps_above_lateral_mu_g_proxy':int(np.sum(accel_proxy>1.)),
            'physical_parameters':physical,'controller_model_parameters':nominal,
            'input_delay_s':delay,'numerical_input_checks_passed':True}
    atomic_json(result_path,result)
    return result


def main():
    protocol=freeze_protocol()
    # Preflight gates are already frozen above; abort without a correction loop on failure.
    import independent_controller_check as check
    check.main();nominal=read_parameters();integration_preflight(nominal)
    conf_data=yaml.safe_load((REPO/'examples/config_example_map.yaml').read_text())
    conf_data['wpt_path']=str((REPO/'examples'/conf_data['wpt_path']).resolve());conf=base.SimpleNamespace(**conf_data)
    w=np.loadtxt(conf.wpt_path,delimiter=';',skiprows=3);geom=base.PathGeometry(w)
    mc=yaml.safe_load((REPO/'examples/example_map.yaml').read_text())
    bitmap=np.flipud(np.array(Image.open(REPO/'examples'/mc['image']).convert('L')))>128
    base.OCCUPIED=~bitmap;clearance=mc['resolution']*distance_transform_edt(bitmap)
    base.verify_rectangular_geometry(mc)
    launch={'state':'running','completed_cases':0,'total_cases':protocol['case_count'],'started_unix':time.time(),
            'host':platform.platform(),'python':sys.version,'pid':os.getpid(),
            'execution':'Sequential cases on shared host; deterministic randomized controller order per scenario/cell.'}
    atomic_json(ROOT/'progress.json',launch);results=[]
    try:
        for ci,cell in enumerate(CELLS):
            physical=nominal.copy();physical['mu']*=cell['mu_factor']
            physical['m']*=cell['mass_I_factor'];physical['I']*=cell['mass_I_factor']
            for scenario in protocol['scenario_draws']:
                order=np.random.default_rng(scenario['seed']*10+ci).permutation(CONTROLLERS)
                for name in order:
                    launch['current']={'cell':cell['name'],'seed':scenario['seed'],'controller':str(name)}
                    atomic_json(ROOT/'progress.json',launch)
                    result=run_case(str(name),nominal,physical,conf,w,geom,clearance,mc,scenario,cell);results.append(result)
                    launch['completed_cases']=len(results);launch['last_outcome']=result['reason'];launch['updated_unix']=time.time()
                    atomic_json(ROOT/'progress.json',launch)
                    print(json.dumps({'case':len(results),'total':protocol['case_count'],'cell':cell['name'],'seed':scenario['seed'],
                                      'controller':str(name),'outcome':result['reason'],'time_s':result['time_s'],
                                      'wall_s':round(result['wall_seconds'],3)}),flush=True)
    except Exception as e:
        launch['state']='stopped_at_first_invalid_check';launch['error']=repr(e);launch['updated_unix']=time.time()
        atomic_json(ROOT/'progress.json',launch)
        raise
    launch['state']='completed';launch['updated_unix']=time.time()
    atomic_json(ROOT/'progress.json',launch);atomic_json(ROOT/'all_results.json',results)

if __name__=='__main__':main()
