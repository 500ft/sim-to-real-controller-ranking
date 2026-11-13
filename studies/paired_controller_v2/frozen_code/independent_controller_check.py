"""Read historical sources; check local plant/controller consistency in scratch.

This does not run laps, inspect real driving data or change the racing repository.
"""
from __future__ import annotations
import ast
import csv
import hashlib
import json
import platform
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.linalg import expm, solve_discrete_are
from scipy.optimize import root

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
SOURCES = [REPO / p for p in [
    "gym/roboracer/controllers.py", "gym/roboracer/dynamics.py",
    "gym/roboracer/closed_loop.py", "gym/f110_gym/envs/dynamic_models.py",
    "gym/f110_gym/envs/base_classes.py", "gym/f110_gym/envs/f110_env.py",
    "experiments/lqr_controller.py", "experiments/mpc_controller.py",
    "experiments/controller_comparison.py", "runs/lqr_controller/linear_model.json",
    "runs/mpc_controller/results.csv", "runs/pure_pursuit_sweep/results.csv",
]]


def read_parameters():
    tree = ast.parse((REPO / "gym/roboracer/dynamics.py").read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEFAULT_DYNAMIC_PARAMS" for t in n.targets):
            return ast.literal_eval(n.value)
    raise RuntimeError("Missing declared parameters")


def tire_rhs(delta, speed, yaw_rate, beta, accel, p):
    """Independent transcription of the source dynamic plant's non-kinematic branch."""
    mu, m, iz, lf, lr, h = (p[k] for k in ("mu", "m", "I", "lf", "lr", "h"))
    cf, cr, g = p["C_Sf"], p["C_Sr"], 9.81
    l = lf + lr
    ff, fr = g * lr - accel * h, g * lf + accel * h
    rd = (-mu*m/(speed*iz*l)*(lf*lf*cf*ff+lr*lr*cr*fr)*yaw_rate
          +mu*m/(iz*l)*(lr*cr*fr-lf*cf*ff)*beta
          +mu*m/(iz*l)*lf*cf*ff*delta)
    bd = ((mu/(speed*speed*l)*(cr*fr*lr-cf*ff*lf)-1)*yaw_rate
          -mu/(speed*l)*(cr*fr+cf*ff)*beta
          +mu/(speed*l)*cf*ff*delta)
    return np.array([rd, bd])


def trim(speed, curvature, p):
    def equations(z):
        delta, beta = z
        # Constant path offset, velocity along the tangent, and r=v*kappa.
        return tire_rhs(delta, speed, speed*curvature, beta, 0.0, p)
    sol = root(equations, [np.arctan((p["lf"]+p["lr"])*curvature), 0.0])
    if not sol.success or np.max(np.abs(equations(sol.x))) > 1e-8:
        raise RuntimeError("Trim failed")
    delta, beta = sol.x
    return {"delta":float(delta), "beta":float(beta), "epsi":float(-beta), "r":float(speed*curvature)}


def frenet_rhs(x, u, speed0, curvature, p, nominal):
    """Coordinates: [ey, epsi-epsi0, delta-delta0, v-v0, r-r0, beta-beta0]."""
    ey, ep, de, dv, dr, db = x
    v, delta = speed0 + dv, nominal["delta"] + de
    beta, epsi, yaw_rate = nominal["beta"]+db, nominal["epsi"]+ep, nominal["r"]+dr
    along_speed = v*np.cos(epsi+beta)/(1-curvature*ey)
    rd, bd = tire_rhs(delta, v, yaw_rate, beta, u[1], p)
    return np.array([v*np.sin(epsi+beta), yaw_rate-curvature*along_speed,
                     u[0], u[1], rd, bd])


def jacobian(function, dimension, step):
    out=[]
    for i in range(dimension):
        dx=np.zeros(dimension); dx[i]=step
        out.append((function(dx)-function(-dx))/(2*step))
    return np.column_stack(out)


def continuous_matrices(speed0, curvature, p, step=1e-6):
    nominal=trim(speed0,curvature,p)
    a=jacobian(lambda x:frenet_rhs(x,np.zeros(2),speed0,curvature,p,nominal),6,step)
    b=jacobian(lambda u:frenet_rhs(np.zeros(6),u,speed0,curvature,p,nominal),2,step)
    return a,b,nominal


def exact_zoh(a,b,dt):
    aug=np.zeros((a.shape[0]+b.shape[1],a.shape[0]+b.shape[1]))
    aug[:6,:6]=a; aug[:6,6:]=b
    e=expm(aug*dt)
    return e[:6,:6],e[:6,6:]


def analytic_straight(speed,p):
    """Derived independently from axle-normal-load linear tire forces."""
    m,mu,g,lf,lr,iz=p['m'],p['mu'],9.81,p['lf'],p['lr'],p['I']
    cf=mu*m*g*lr/(lf+lr)*p['C_Sf']
    cr=mu*m*g*lf/(lf+lr)*p['C_Sr']
    a=np.zeros((6,6)); b=np.zeros((6,2))
    a[0,1]=a[0,5]=speed; a[1,4]=1
    b[2,0]=b[3,1]=1
    a[4,2]=lf*cf/iz; a[4,4]=-(lf*lf*cf+lr*lr*cr)/(iz*speed)
    a[4,5]=(-lf*cf+lr*cr)/iz
    a[5,2]=cf/(m*speed); a[5,4]=(-lf*cf+lr*cr)/(m*speed*speed)-1
    a[5,5]=-(cf+cr)/(m*speed)
    return a,b,{"front_force_stiffness_N_per_rad":cf,"rear_force_stiffness_N_per_rad":cr}


def actual_source_gradient_test(payload):
    tree=ast.parse((REPO/'gym/roboracer/controllers.py').read_text())
    method=next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='MPCController'
                for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='_cost_and_grad')
    module=ast.Module(body=[method],type_ignores=[])
    ns={'np':np};exec(compile(module,'controllers.py:_cost_and_grad','exec'),ns)
    model=SimpleNamespace(a_d=np.array(payload['A_discrete']),b_d=np.array(payload['B_discrete']),
                          q=np.diag(payload['q_diag']),r=np.diag(payload['r_diag']))
    obj=SimpleNamespace(horizon=15,model=model)
    rng=np.random.default_rng(88317); rows=[]
    for case in range(3):
        x=rng.normal(0,.1,6); z=rng.normal(0,.1,30)
        fun=lambda q:ns['_cost_and_grad'](obj,q,x)
        value,grad=fun(z)
        fd=np.zeros_like(z)
        for i in range(len(z)):
            e=np.zeros_like(z);e[i]=1e-5
            fd[i]=(fun(z+e)[0]-fun(z-e)[0])/(2e-5)
        err=float(np.max(np.abs(fd-grad)))
        rows.append({'case':case,'cost':float(value),'max_abs_gradient_error':err,'passes_1e-6':err<=1e-6})
    return rows


def main():
    start=time.perf_counter(); p=read_parameters()
    historical=json.loads((REPO/'runs/lqr_controller/linear_model.json').read_text())
    speed=historical['operating_speed_mps'];curv=historical['operating_curvature_1pm'];dt=.01
    a0,b0,_=continuous_matrices(speed,0.,p)
    aa,bb,stiff=analytic_straight(speed,p)
    analytic_error=float(max(np.max(np.abs(a0-aa)),np.max(np.abs(b0-bb))))
    ac,bc,nom=continuous_matrices(speed,curv,p)
    ac2,bc2,_=continuous_matrices(speed,curv,p,1e-5)
    jac_step_error=float(max(np.max(np.abs(ac-ac2)),np.max(np.abs(bc-bc2))))
    ad,bd=exact_zoh(ac,bc,dt)
    q=np.diag(historical['q_diag']);r=np.diag(historical['r_diag'])
    pp=solve_discrete_are(ad,bd,q,r); k=np.linalg.solve(r+bd.T@pp@bd,bd.T@pp@ad)
    eig=np.linalg.eigvals(ad-bd@k)
    olda=np.array(historical['A_continuous']); oldb=np.array(historical['B_continuous'])
    oldad=np.array(historical['A_discrete']); oldbd=np.array(historical['B_discrete']);oldk=np.array(historical['K'])
    oldeig=np.linalg.eigvals(oldad-oldbd@oldk)
    # Transform the consistent fixed-trim r coordinate into historical r-v*kappa.
    t=np.eye(6);t[4,3]=-curv
    plant_oldcoord=t@ac@np.linalg.inv(t); b_oldcoord=t@bc
    changed=[]
    for i,j in np.argwhere(np.abs(plant_oldcoord-olda)>1e-7):
        changed.append({'row':int(i),'column':int(j),'historical':float(olda[i,j]),'plant_jacobian_same_perturbation_coordinates':float(plant_oldcoord[i,j])})
    csvrow=next(csv.DictReader((REPO/'runs/mpc_controller/results.csv').open()))
    grad=actual_source_gradient_test(historical)
    result={
      'scope':'Independent local controller model audit. No laps or real driving outcomes read.',
      'source_parameters':p,'operating_speed_mps':speed,'operating_curvature_1pm':curv,
      'force_stiffness':stiff,'curved_trim':nom,
      'straight_analytic_vs_finite_difference_max_abs_error':analytic_error,
      'curved_jacobian_step_sensitivity_max_abs_error':jac_step_error,
      'acceptance':{'straight_jacobian_limit':1e-6,'straight_jacobian_pass':analytic_error<=1e-6,
                    'curved_step_limit':1e-6,'curved_step_pass':jac_step_error<=1e-6,
                    'mpc_objective_gradient_limit':1e-6,'all_gradient_checks_pass':all(x['passes_1e-6'] for x in grad)},
      'historical_recomputed_poles':[{'real':float(x.real),'imag':float(x.imag),'abs':float(abs(x))}for x in oldeig],
      'historical_max_pole_abs':float(max(abs(oldeig))),
      'candidate_ideal_rate_input_max_pole_abs':float(max(abs(eig))),
      'candidate_ideal_rate_input_poles':[{'real':float(x.real),'imag':float(x.imag),'abs':float(abs(x))}for x in eig],
      'candidate_pole_scope':'Ideal direct steering-rate/acceleration state feedback only. Does not qualify PP feedforward, clipping, the integrated corrections, low-level bang-bang steering or speed PID in the actual historical runner.',
      'historical_A_mismatches':changed,
      'mpc_objective_gradient_checks':grad,
      'historical_timing':{k:csvrow[k] for k in csvrow if k.startswith('mpc_')},
      'historical_deadline_miss_lower_bound':1,
      'historical_exact_deadline_miss_count':None,'historical_p50_solve_time':None,
      'exact_zoh_A':ad.tolist(),'exact_zoh_B':bd.tolist(),'candidate_K':k.tolist(),
      'elapsed_seconds':time.perf_counter()-start,
      'source_manifest':{str(x.relative_to(REPO)):hashlib.sha256(x.read_bytes()).hexdigest() for x in SOURCES}
    }
    (HERE/'controller_validity_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'straight_jacobian_error':analytic_error,'curved_jacobian_step_error':jac_step_error,
                      'historical_max_pole':result['historical_max_pole_abs'],
                      'candidate_ideal_max_pole':result['candidate_ideal_rate_input_max_pole_abs'],
                      'gradient_checks':grad,'elapsed_seconds':result['elapsed_seconds']}))
    if not all([result['acceptance']['straight_jacobian_pass'],result['acceptance']['curved_step_pass'],result['acceptance']['all_gradient_checks_pass']]):
        raise RuntimeError('Independent analytical gate failed')

if __name__=='__main__':main()
