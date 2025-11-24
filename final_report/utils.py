from pyomo.environ import *
import pandas as pd
import numpy as np
import rainflow
from sklearn.preprocessing import StandardScaler

def model():
    # Initialize model
    m = AbstractModel()

    # Sets
    m.T = Set()                # Time (h)

    # Parameters
    m.price = Param(m.T)       # RTM ($)
    m.C = Param()              # C-rate
    m.Q_rem = Param()          # Capacity Remaining (MWh)
    m.soc_0 = Param()          # Initial State of Charge (MWh)
    m.dod_min = Param()        # Minimum Depth of Discharge (0-1)
    m.dod_max = Param()        # Maximum Depth of Discharge (0-1)
    m.efficiency = Param()     # One-Way Efficiency (0-1)
    m.delta_t = Param()        # Timestep (hr)

    # Variables
    m.charge = Var(m.T, within=NonNegativeReals)        # Power Charging (MW)
    m.discharge = Var(m.T, within=NonNegativeReals)     # Power Discharging (MW)
    m.soc = Var(m.T, within=NonNegativeReals)           # State of Charge (Mwh)
    m.is_charging = Var(m.T, within=Binary)             # Charging Indicator (0, 1)
    m.grid_transaction = Var(m.T, within=Reals)         # Net Revenue / Expense ($)

    # Constraints
    # SOC Balance
    def soc_balance_rule(m, t):
        if t == m.T.first():
            return m.soc[t] == (1 - m.dod_max) * m.Q_rem + (m.charge[t] * m.efficiency - m.discharge[t] / m.efficiency) * m.delta_t
        else:
            return m.soc[t] == m.soc[m.T.prev(t)] + (m.charge[t] * m.efficiency - m.discharge[t] / m.efficiency) * m.delta_t
    m.soc_balance = Constraint(m.T, rule=soc_balance_rule)

    # Charge Limit
    def charge_limit_rule(m, t):
        return m.charge[t] <= m.Q_rem * m.C * m.is_charging[t]
    m.charge_limit_1 = Constraint(m.T, rule=charge_limit_rule)

    # Discharge Limit
    def discharge_limit_rule(m, t):
        return m.discharge[t] <= m.Q_rem * m.C * (1 - m.is_charging[t])
    m.discharge_limit_1 = Constraint(m.T, rule=discharge_limit_rule)

    # SOC Max
    def soc_max_rule(m, t):
        return m.soc[t] <= (1 - m.dod_min) * m.Q_rem 
    m.soc_max_constraint_2 = Constraint(m.T, rule=soc_max_rule)

    # SOC Min
    def soc_min_rule(m, t):
        return m.soc[t] >= (1 - m.dod_max) * m.Q_rem
    m.soc_min_constraint = Constraint(m.T, rule=soc_min_rule)

    # Grid Transaction
    def grid_transaction_rule(m, t):
        return m.grid_transaction[t] == m.price[t] * (m.discharge[t] - m.charge[t]) * m.delta_t
    m.grid_transaction_constraint = Constraint(m.T, rule=grid_transaction_rule)

    # Objective
    def total_grid_transaction_rule(m):
        return sum(m.grid_transaction[t] for t in m.T)
    m.cost = Objective(rule=total_grid_transaction_rule, sense=maximize)

    return m

def run_model(parameters, degradation):
    
    # Initial Capacity
    Q_B = parameters['capacity']

    # Read price data
    rtm = pd.read_csv('rtm_2024.csv', parse_dates=['Time'])

    # Data Frame to store results
    results = pd.DataFrame()

    # Loop over 48-hr windows starting every 24 hrs
    for day in range(365):
        rtm_window = rtm[day * 96 : (day + 2) * 96]

        window_price = rtm_window['Settlement Point Price'].values

        # Data for model instance
        data = { None: {
            'T': {None: list(range(1, len(rtm_window) + 1))},
            'price': {t+1: window_price[t] for t in range(len(window_price))},
            'C' : {None: 1 / parameters['duration']},
            'Q_rem': {None: parameters['capacity']},
            'dod_min': {None: parameters['dod_min']},
            'dod_max': {None: parameters['dod_max']},
            'efficiency': {None: parameters['efficiency']},
            'delta_t': {None: parameters['delta_t']},
        }}

        # Create instance
        instance = model().create_instance(data)

        # Solve
        SolverFactory('gurobi').solve(instance)

        day_charge = [instance.charge[t]() for t in range(1, 97)]
        day_discharge = [instance.discharge[t]() for t in range(1, 97)]
        day_soc = [instance.soc[t]() for t in range(1, 97)]
        day_grid_transaction = [instance.grid_transaction[t]() for t in range(1, 97)]

        # Create DataFrame for the day's results
        day_results = pd.DataFrame({
            "Price ($/MWh)": window_price[:96],
            "Charge (MW)": day_charge,
            "Discharge (MW)": day_discharge,
            "SOC (MWh)": day_soc,
            "Grid Transaction ($)": day_grid_transaction
        })

        # Calculate degradation (0-1) based on chosen method
        # Calendar
        if degradation == 'calendar':
            delta_Q = calendar_degradation(
                lifetime= parameters['lifetime'], 
                eol= parameters['eol'], 
                delta_t= parameters['delta_t']
            )
        
        # Throughput
        elif degradation == 'throughput':
            delta_Q = throughput_degradation(
                fade_factor= parameters['fade_factor'],
                charge= day_charge,
                discharge= day_discharge,
                Q_B= Q_B,
                delta_t= parameters['delta_t']
            )
        
        # Rainflow
        elif degradation == 'rainflow':
            delta_Q = rainflow_degradation(
                a= parameters['a'],
                b= parameters['b'],
                Q_B = Q_B,
                soc = day_soc
            )
        
        else:
            raise ValueError(f"{degradation} is not a valid degradation argument. Must be one of ['calendar', 'throughput', 'rainflow']")
        
        # Add degradation to day results DataFrame
        day_results['Capacity Degradation (MWh)'] = delta_Q * Q_B
        
        # Append day's results to overall results
        # check if empty DataFrame
        if results.empty:
            results = day_results
        else:
            results = pd.concat([results, day_results])

        # Update initial SOC and remaining capacity for next day
        parameters['soc_0'] = instance.soc[96]()
        parameters['capacity'] -= sum(delta_Q) * Q_B

    # Calculate replacement cost from parameters
    replace_cost = (240.8 * parameters['duration'] + 379.16) * (Q_B / parameters['duration']) * 1000 

    # Add degradation cost to results DataFrame
    results['Degradation Cost ($)'] =  replace_cost * results['Capacity Degradation (MWh)'] / ((1 - parameters['eol']) * Q_B)
    
    # Add remaining capacity to results DataFrame
    results['Remaining Capacity (%)'] = (Q_B - np.cumsum(results['Capacity Degradation (MWh)'])) / Q_B


    # Set datetime index
    results.index = rtm['Time'][0:len(results)]

    return results    

def calendar_degradation(lifetime, eol, delta_t):
    return np.array([(1 - eol) / lifetime / 365 / 24 * delta_t for _ in range(96)])

def throughput_degradation(fade_factor, charge, discharge, Q_B, delta_t):
    return fade_factor * (np.array(charge) + np.array(discharge)) / Q_B / 2 * delta_t

def rainflow_degradation(a, b, soc, Q_B):
    
    # Extract rainflow cycles
    cycles = np.array(rainflow.count_cycles(np.array(soc) / Q_B))

    delta_Q_total = sum((a * (cycles[:,0] ** b)) * cycles[:,1])

    # Spread degradation uniformly across timesteps
    return np.array([delta_Q_total / len(soc)] * len(soc))
