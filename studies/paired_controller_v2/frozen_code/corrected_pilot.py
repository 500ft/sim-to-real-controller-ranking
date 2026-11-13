"""Fresh direct-rate synthetic benchmark pilot; historical results stay unchanged.

Loads the public source plant equations and waypoint planner read-only.  It does
not use the historical F110 wrapper, its two-circuit finish rule or raw datasets.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import ast
import csv
import hashlib
import json
import math
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
from scipy.linalg import solve_discrete_are
from scipy.ndimage import distance_transform_edt
from scipy.optimize import Bounds, LinearConstraint, minimize
import yaml

from independent_controller_check import REPO, HERE, read_parameters, continuous_matrices, exact_zoh

DT=.002
CONTROL_DT=.01
HOLD=5
HORIZON=15
MAX_TIME=45.
PILOT_SEED=883170
OUT=HERE/'pilot_v2'


def load_source_functions():
    text=(REPO/'gym/f110_gym/envs/dynamic_models.py').read_text()
    tree=ast.parse(text)
    names={'accl_constraints','steering_constraint','vehicle_dynamics_ks','vehicle_dynamics_st','pid'}
    nodes=[]
    for n in tree.body:
        if isinstance(n,ast.FunctionDef) and n.name in names:
            n.decorator_list=[];nodes.append(n)
    ns={'np':np};exec(compile(ast.Module(body=nodes,type_ignores=[]),'source_dynamic_models.py','exec'),ns)
    # Pure pursuit is loaded without importing the Gym package.
    track_ns={'np':np,'Namespace':SimpleNamespace}
    tr=ast.parse((REPO/'gym/roboracer/track.py').read_text())
    wanted={'nearest_point_on_trajectory','first_point_on_trajectory_intersecting_circle','get_actuation','PurePursuitPlanner'}
    tn=[n for n in tr.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in wanted]
    exec(compile(ast.Module(body=tn,type_ignores=[]),'source_track.py','exec'),track_ns)
    return ns,track_ns['PurePursuitPlanner']


class PathGeometry:
    def __init__(self,w):
        self.w=w;self.xy=w[:,1:3];self.starts=self.xy[:-1];self.seg=np.diff(self.xy,axis=0)
        self.lengths=np.linalg.norm(self.seg,axis=1);self.length=float(w[-1,0]);self.n=len(self.seg)
        self.sq=self.lengths**2;self.head=np.arctan2(self.seg[:,1],self.seg[:,0])
    def at(self,position):
        t=np.clip(np.sum((position-self.starts)*self.seg,axis=1)/self.sq,0.,1.)
        pts=self.starts+self.seg*t[:,None];idx=int(np.argmin(np.sum((position-pts)**2,axis=1)))
        d=position-pts[idx];ey=(self.seg[idx,0]*d[1]-self.seg[idx,1]*d[0])/self.lengths[idx]
        # A fixed 1.2 m central geometric curvature stencil reduces waypoint noise.
        prev=(idx-3)%self.n;nxt=(idx+3)%self.n
        dh=wrap(self.head[nxt]-self.head[prev]);span=sum(self.lengths[(prev+j)%self.n] for j in range(6))
        curv=dh/span
        progress=float(self.w[idx,0]+t[idx]*(self.w[idx+1,0]-self.w[idx,0]))
        return {'index':idx,'ey':float(ey),'heading':float(self.head[idx]),'curvature':float(curv),'progress':progress,
                'profile_speed':float(self.w[idx,5])}


def wrap(a):return (a+np.pi)%(2*np.pi)-np.pi


class ModelCache:
    def __init__(self,p):self.p=p;self.cache={}
    def get(self,v,kappa):
        key=(max(2.,round(v*2)/2),round(kappa/.02)*.02)
        if key not in self.cache:
            a,b,nom=continuous_matrices(key[0],key[1],self.p)
            ad,bd=exact_zoh(a,b,CONTROL_DT)
            q=np.diag([20.,12.,1.,.5,2.,2.]);r=np.diag([2.,.5])
            pp=solve_discrete_are(ad,bd,q,r)
            gain=np.linalg.solve(r+bd.T@pp@bd,bd.T@pp@ad)
            if max(abs(np.linalg.eigvals(ad-bd@gain)))>=1.:
                raise RuntimeError('Ideal scheduled model is not stable')
            phi=np.vstack([np.linalg.matrix_power(ad,i+1) for i in range(HORIZON)])
            gamma=np.zeros((6*HORIZON,2*HORIZON))
            for i in range(HORIZON):
                for j in range(i+1):gamma[6*i:6*i+6,2*j:2*j+2]=np.linalg.matrix_power(ad,i-j)@bd
            qbar=np.kron(np.eye(HORIZON),q);qbar[-6:,-6:]=pp
            rb=np.kron(np.eye(HORIZON),r)
            hess=2*(gamma.T@qbar@gamma+rb)
            self.cache[key]=(ad,bd,gain,nom,phi,gamma,qbar,hess)
        return key,self.cache[key]


def actual_trim(v,kappa,p):
    # Linear zero-acceleration tire equations: solve two equations for delta,beta.
    from independent_controller_check import tire_rhs
    r=v*kappa;base=tire_rhs(0.,v,r,0.,0.,p)
    mat=np.column_stack((tire_rhs(1.,v,r,0.,0.,p)-base,tire_rhs(0.,v,r,1.,0.,p)-base))
    delta,beta=np.linalg.solve(mat,-base)
    return float(delta),float(beta)


class RateController:
    def __init__(self,name,p,planner,cache,speed_scale=1.2):
        self.name=name;self.p=p;self.planner=planner;self.cache=cache;self.scale=speed_scale
        self.last=np.zeros((HORIZON,2));self.timings=[];self.flags=[];self.startup_count=0
    def pp_u(self,state):
        speed,steer=self.planner.plan(float(state[0]),float(state[1]),float(state[4]),1.2,self.scale)
        accel,rate=SOURCE['pid'](speed,steer,state[3],state[2],self.p['sv_max'],self.p['a_max'],self.p['v_max'],self.p['v_min'])
        return np.array([rate,accel])
    def command(self,state,info):
        start=time.perf_counter()
        if self.name=='pure_pursuit' or state[3]<2.:
            u=self.pp_u(state)
            if self.name!='pure_pursuit':self.startup_count+=1
        else:
            vref=self.scale*info['profile_speed'];kappa=info['curvature']
            delta_ref,beta_ref=actual_trim(vref,kappa,self.p)
            # Fixed-trim yaw-rate coordinate; no double subtraction of kappa*dv.
            x=np.array([info['ey'],wrap(state[4]-info['heading']+beta_ref),state[2]-delta_ref,
                        state[3]-vref,state[5]-vref*kappa,state[6]-beta_ref])
            _,model=self.cache.get(vref,kappa)
            ad,bd,gain,nom,phi,gamma,qbar,hess=model
            if self.name=='lqr':u=-gain@x
            else:
                f=2*gamma.T@qbar@(phi@x)
                z0=np.vstack([self.last[1:],self.last[-1:]]).ravel()
                rows=[];lo=[];hi=[]
                free=phi@x
                for i in range(HORIZON):
                    rows.append(gamma[6*i+2]);lo.append(self.p['s_min']-delta_ref-free[6*i+2]);hi.append(self.p['s_max']-delta_ref-free[6*i+2])
                    rows.append(gamma[6*i+3]);lo.append(-vref-free[6*i+3]);hi.append(self.p['v_max']-vref-free[6*i+3])
                apos=min(self.p['a_max'],self.p['a_max']*self.p['v_switch']/max(state[3],self.p['v_switch']))
                bounds=Bounds(np.tile([self.p['sv_min'],-self.p['a_max']],HORIZON),np.tile([self.p['sv_max'],apos],HORIZON))
                constraint=LinearConstraint(np.array(rows),np.array(lo),np.array(hi))
                result=minimize(lambda z:(.5*z@hess@z+f@z,hess@z+f),z0,jac=True,method='SLSQP',
                                bounds=bounds,constraints=[constraint],options={'ftol':1e-6,'maxiter':80,'disp':False})
                self.flags.append(bool(result.success))
                if not result.success:raise RuntimeError('MPC optimizer failed: '+result.message)
                zz=result.x;cv=np.array(rows)@zz
                if np.max(np.maximum(np.array(lo)-cv,cv-np.array(hi)))>1e-6:
                    raise RuntimeError('MPC predicted state constraint violation')
                self.last=zz.reshape(HORIZON,2);u=self.last[0]
        self.timings.append(time.perf_counter()-start)
        return np.array([np.clip(u[0],self.p['sv_min'],self.p['sv_max']),
                         np.clip(u[1],-self.p['a_max'],self.p['a_max'])])


def derivative(x,u,p):
    return SOURCE['vehicle_dynamics_st'](x,u,*[p[k] for k in ['mu','C_Sf','C_Sr','lf','lr','h','m','I','s_min','s_max','sv_min','sv_max','v_switch','a_max','v_min','v_max']])


def step(x,u,p):
    k1=derivative(x,u,p);k2=derivative(x+DT*k1/2,u,p);k3=derivative(x+DT*k2/2,u,p);k4=derivative(x+DT*k3,u,p)
    return x+DT*(k1+2*k2+2*k3+k4)/6


def protocol():
    # Written before any pilot result, and frozen separately from controller outcomes.
    return {
      'version':'racing-v2-direct-rate-pilot-20261113','scope':'Synthetic public example track; no historical outcome replay or real data.',
      'plant':'Read-only source vehicle_dynamics_st, source constraints, RK4 dt=.002s. Perfect plant state available to every controller.',
      'architecture':{'pure_pursuit':'Source PP lookahead1.2, speed profile gain1.2; source pid/steering relay maps target angle/speed to physical rate/acceleration at100Hz.',
                      'lqr':'Standalone scheduled Frenet full-state feedback on direct steering-rate/acceleration with steady-turn feedforward and common PP startup below2m/s.',
                      'mpc':'Standalone constrained linear MPC on corrected scheduled Frenet model;15 steps, exact ZOH, state/input bounds, shifted feasible warm start; common PP startup below2m/s.'},
      'interface_difference':'Historical F110 wrapper applies relay/PID every2ms and a steering-target buffer. New study maps PP at100Hz and applies the same4ms physical input delay to all controllers; it does not reproduce the wrapper.',
      'controller_dt_s':CONTROL_DT,'integration_dt_s':DT,'input_delay_s':.004,'horizon':15,
      'model_schedule':{'speed_grid_mps':.5,'curvature_grid_1pm':.02,'linearization':'Finite-difference Jacobian of full nonlinear Frenet plant at a consistent steady-turn trim; exact ZOH.',
                        'curvature_stencil':'Geometric central6-segment span, about1.2m; fixed before outcomes.'},
      'completion':'One unwrapped geometric progress circuit >=156.3586m, rather than historical toggle>=4 episode.',
      'collision':'Conservative map distance-to-obstacle at center <=circumscribed vehicle radius; no source LiDAR TTC. Same screen for all controllers.',
      'pilot':{'seed':PILOT_SEED,'lateral_offset_m':0.,'heading_offset_rad':0.,'speed_profile_multiplier':1.,'max_time_s':MAX_TIME},
      'campaign_not_launched':{'paired_seeds':list(range(883200,883220)),
                               'draws':'PCG64 per seed: initial lateral error U[-.10,.10]m; heading error U[-2,2]deg; profile-speed multiplier U[.95,1.05]. Scenario realization shared by controllers.',
                               'robustness_OAT':{'friction_mu_factor':[.8,1.2],'coherent_mass_and_I_factor':[.9,1.1],'additional_delay_ms':[10,30]},
                               'purpose':'Conditional synthetic architecture comparison; intervals over declared scenario draws, not a population or real-platform ranking.'},
      'acceptance_before_pilot':{'independent_jacobian_and_gradient':'All independent_controller_check.py fixed1e-6 gates pass.',
                                 'finite_state':True,'input_rate_bound_radps':3.2,'input_acceleration_bound_mps2':9.51,
                                 'state_bound_tolerance':'Source clamp allows one integration-step overshoot: sv_max*DT and a_max*DT.',
                                 'optimizer':'Stop on first solver failure or >1e-6 predicted-constraint violation; no tuning/retry.',
                                 'case_completion':'Report collision/timeout as a negative pilot outcome, not a numerical pass or an excluded draw.',
                                 'timing':'Retain every full controller-call time, including model cache miss, p50,p95,max and count>10ms. Timing alone is not hard-real-time qualification.'}}


def run(name,p,conf,w,geom,clearance,map_conf,cache):
    planner=Planner(conf,p['lf']+p['lr']);controller=RateController(name,p,planner,cache)
    heading=geom.at(w[0,1:3])['heading']
    x=np.array([w[0,1],w[0,2],0.,0.,heading,0.,0.])
    prev=geom.at(x[:2])['progress'];progress=0.;u=np.zeros(2);queue=deque([u.copy(),u.copy()])
    trace=[];wall=time.perf_counter();reason='timeout';radius=math.hypot(.58/2,.31/2)
    for i in range(int(MAX_TIME/DT)):
        info=geom.at(x[:2])
        if i%HOLD==0:u=controller.command(x,info)
        queue.append(u.copy());applied=queue.popleft()
        x=step(x,applied,p)
        if not np.all(np.isfinite(x)):raise RuntimeError('Nonfinite state')
        if abs(x[2])>p['s_max']+p['sv_max']*DT+1e-8:raise RuntimeError('Steering state exceeds registered integration tolerance')
        new_info=geom.at(x[:2]);ds=new_info['progress']-prev
        if ds < -geom.length/2:ds+=geom.length
        elif ds>geom.length/2:ds-=geom.length
        progress+=ds;prev=new_info['progress']
        col=int((x[0]-map_conf['origin'][0])/map_conf['resolution']);row=int((x[1]-map_conf['origin'][1])/map_conf['resolution'])
        gap=clearance[row,col] if 0<=row<clearance.shape[0] and 0<=col<clearance.shape[1] else 0.
        trace.append([DT*(i+1),*x,*applied,new_info['ey'],progress,gap])
        if gap<=radius:reason='conservative_map_collision';break
        if progress>=geom.length:reason='one_circuit';break
    arr=np.array(trace)
    np.savetxt(OUT/(name+'_trace.csv'),arr,delimiter=',',header='time_s,x_m,y_m,steer_rad,v_mps,yaw_rad,yaw_rate_radps,beta_rad,applied_steer_rate_radps,applied_acceleration_mps2,cte_m,unwrapped_progress_m,obstacle_center_distance_m',comments='')
    np.savetxt(OUT/(name+'_controller_times_s.csv'),np.array(controller.timings),delimiter=',',header='full_controller_call_seconds',comments='')
    times=np.array(controller.timings)
    result={'controller':name,'reason':reason,'completed_one_circuit':reason=='one_circuit','time_s':float(arr[-1,0]),
            'progress_m':float(progress),'rms_cte_m':float(np.sqrt(np.mean(arr[:,10]**2))),'max_abs_cte_m':float(max(abs(arr[:,10]))),
            'mean_speed_mps':float(arr[:,4].mean()),'wall_seconds':time.perf_counter()-wall,
            'control_calls':len(times),'full_call_p50_ms':float(np.quantile(times,.5)*1000),
            'full_call_p95_ms':float(np.quantile(times,.95)*1000),'full_call_max_ms':float(max(times)*1000),
            'calls_over_10ms':int(np.sum(times>.01)),'common_PP_startup_calls':controller.startup_count,
            'mpc_successful_solves':len(controller.flags),'cached_models':len(cache.cache)}
    (OUT/(name+'_result.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result


SOURCE,Planner=load_source_functions()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    reg=OUT/'protocol.json'
    current=protocol()
    if reg.exists() and json.loads(reg.read_text())!=current:raise RuntimeError('Frozen protocol differs')
    reg.write_text(json.dumps(current,indent=2)+'\n')
    import independent_controller_check
    independent_controller_check.main()
    conf_data=yaml.safe_load((REPO/'examples/config_example_map.yaml').read_text())
    conf_data['wpt_path']=str((REPO/'examples'/conf_data['wpt_path']).resolve());conf=SimpleNamespace(**conf_data)
    w=np.loadtxt(conf.wpt_path,delimiter=';',skiprows=3);geom=PathGeometry(w);p=read_parameters()
    mc=yaml.safe_load((REPO/'examples/example_map.yaml').read_text())
    bitmap=np.flipud(np.array(Image.open(REPO/'examples'/mc['image']).convert('L')))>128
    clearance=mc['resolution']*distance_transform_edt(bitmap)
    # Separate fresh caches: setup overhead is counted consistently in full-call timing.
    names=sys.argv[1:] or ['pure_pursuit','lqr','mpc'];results=[]
    for name in names:
        result=run(name,p,conf,w,geom,clearance,mc,ModelCache(p));results.append(result)
        print(json.dumps(result),flush=True)
        if not result['completed_one_circuit']:
            raise RuntimeError('Negative pilot outcome; stop before next controller, do not tune after outcome')
    (OUT/'pilot_summary.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':main()
