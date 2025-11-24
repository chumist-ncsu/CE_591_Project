from utils import run_model
model_parameters = {
    'capacity': 2,      # MWh
    'duration': 4,      # hr
    'soc_0': 0,         # MWh
    'dod_min': 0.1,     # 0-1
    'dod_max': 0.9,     # 0-1
    'efficiency': 0.85,  # 0-1
    'delta_t': 0.25     # hr
}
calendar_parameters = model_parameters.copy()
calendar_parameters.update({
    'lifetime': 10,      # years
    'eol': 0.8           # 0-1
})
run_model(calendar_parameters, 'calendar')