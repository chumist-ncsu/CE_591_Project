import pandas as pd
from pyomo.environ import *

def get_results(model, parameters):
    
    # Read price data
    rtm = pd.read_csv("rtm_2024.csv", parse_dates=["Time"])

    # Data Frame to store results
    bess_results = pd.DataFrame()

    # Loop over 48-hr windows starting every 24 hrs
    for day in range(365):
        rtm_2_day = rtm[day*96:(day+2)*96]

        # Calculate replacement cost from parameters
        replace_cost = (240.8 * parameters["duration"] + 379.16) * (parameters["capacity"] / parameters["duration"]) * 1000 
        
        # Data for model instance
        data = { None: {
            'T': {None: list(range(1, len(rtm_2_day) + 1))},
            'price': {t+1: rtm_2_day["Settlement Point Price"].values[t] for t in range(len(rtm_2_day))},
            'C' : {None: 1 / parameters["duration"]},
            'capacity' : {None: parameters["capacity"]},
            'Q_0': {None: (1 - parameters["dod_min"]) * parameters["capacity"]},
            'soc_0': {None: parameters["soc_0"]},
            'dod_min': {None: parameters["dod_min"]},
            'dod_max': {None: parameters["dod_max"]},
            'efficiency': {None: parameters["efficiency"]},
            'fade_factor': {None: parameters["fade_factor"]},
            'delta_t': {None: 0.25},
            'replace_cost': {None: replace_cost},
            'eol': {None: parameters["eol"]},
        }
        }

        # Create instance
        instance = model.create_instance(data)

        # Solve
        solver = SolverFactory('gurobi')

        # Get results
        results = solver.solve(instance)

        # Create DataFrame for the day's results
        day_results = pd.DataFrame.from_dict(
            {t: (
                instance.price[t],
                instance.charge[t](), 
                instance.discharge[t](), 
                instance.soc[t](), 
                instance.grid_transaction[t](), 
                instance.degradation_cost[t](),
                instance.profit[t](),
                instance.Q[t]() * 100
            ) for t in range(1, 97)
            }, 
            orient='index', 
            columns=[
                'Price ($/MWh)',
                'Charge (MW)', 
                'Discharge (MW)', 
                'SOC (MWh)', 
                'Grid Transaction ($)', 
                'BESS Degradation Cost ($)',
                'Profit ($)',
                'Remaining Capacity (%)'
            ]
        )

        # Append day's results to overall results
        # check if empty DataFrame
        if bess_results.empty:
            bess_results = day_results
        else:
            bess_results = pd.concat([bess_results, day_results])

        # Update initial SOC and capacity for next day
        parameters["soc_0"] = instance.soc[96]()
        parameters["capacity"] = parameters["capacity"] * instance.Q[96]()

    # Set datetime index
    bess_results.index = rtm["Time"][0:len(bess_results)]
    
    return bess_results   