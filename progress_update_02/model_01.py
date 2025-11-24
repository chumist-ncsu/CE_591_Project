from pyomo.environ import *
def model01():
    # Initialize model
    m = AbstractModel()

    # Sets
    m.T = Set()

    # Parameters
    m.price = Param(m.T)
    m.C = Param()
    m.Q_B = Param()
    m.Q_rem = Param()
    m.capacity = Param()
    m.soc_0 = Param()
    m.dod_min = Param()
    m.dod_max = Param()
    m.efficiency = Param()
    m.fade_factor = Param()
    m.delta_t = Param()
    m.replace_cost = Param()
    m.eol = Param()
    m.lifetime = Param()
    m.big_M = Param(initialize= 1e6)


    # Variables
    m.charge = Var(m.T, within=NonNegativeReals)
    m.discharge = Var(m.T, within=NonNegativeReals)
    m.soc = Var(m.T, within=NonNegativeReals)
    m.Q = Var(m.T, within=NonNegativeReals)
    m.delta_Q = Var(m.T, within=NonNegativeReals)
    m.is_charging = Var(m.T, within=Binary)
    m.degradation_cost = Var(m.T, within=NonNegativeReals)
    m.grid_transaction = Var(m.T, within=Reals)
    m.profit = Var(m.T, within=Reals)


    # Constraints
    def soc_balance_rule(m, t):
        if t == m.T.first():
            return m.soc[t] == m.soc_0 + (m.charge[t] * m.efficiency - m.discharge[t] / m.efficiency) * m.delta_t
        else:
            return m.soc[t] == m.soc[m.T.prev(t)] + (m.charge[t] * m.efficiency - m.discharge[t] / m.efficiency) * m.delta_t
    m.soc_balance = Constraint(m.T, rule=soc_balance_rule)

    def charge_limit_rule_1(m, t):
        return m.charge[t] <= m.Q[t] * m.C
    m.charge_limit_1 = Constraint(m.T, rule=charge_limit_rule_1)
    
    def charge_limit_rule_2(m, t):
        return m.charge[t] <= m.is_charging[t] * m.big_M
    m.charge_limit_2 = Constraint(m.T, rule = charge_limit_rule_2)

    def discharge_limit_rule_1(m, t):
        return m.discharge[t] <= m.Q[t] * m.C
    m.discharge_limit_1 = Constraint(m.T, rule=discharge_limit_rule_1)

    def discharge_limit_rule_2(m, t):
        return m.discharge[t] <= (1 - m.is_charging[t]) * m.big_M
    m.discharge_limit_2 = Constraint(m.T, rule = discharge_limit_rule_2)

    def soc_max_rule_1(m, t):
        return m.soc[t] <= m.Q[t] * m.Q_B
    m.soc_max_constraint_1 = Constraint(m.T, rule=soc_max_rule_1)

    def soc_max_rule_2(m, t):
        return m.soc[t] <= (1 - m.dod_min) * m.Q_B 
    m.soc_max_constraint_2 = Constraint(m.T, rule=soc_max_rule_2)

    def soc_min_rule(m, t):
        return m.soc[t] >= (1 - m.dod_max) * m.Q_B
    m.soc_min_constraint = Constraint(m.T, rule=soc_min_rule)

    def delta_Q_rule(m, t):
        return m.delta_Q[t] == m.fade_factor * (m.charge[t] + m.discharge[t]) / m.Q_B / 2 * m.delta_t
    m.delta_Q_constraint = Constraint(m.T, rule=delta_Q_rule)

    def capacity_remaining_rule(m, t):
        if t == m.T.first():
            return m.Q[t] == m.Q_rem
        else:
            return m.Q[t] == m.Q[m.T.prev(t)] - m.delta_Q[t]
    m.capacity_remaining_constraint = Constraint(m.T, rule=capacity_remaining_rule)

    def degradation_cost_rule(m, t):
        return m.degradation_cost[t] == m.delta_Q[t] * m.replace_cost / (1.0 - m.eol)
    m.degradation_cost_constraint = Constraint(m.T, rule=degradation_cost_rule)

    def grid_transaction_rule(m, t):
        return m.grid_transaction[t] == m.price[t] * (m.discharge[t] - m.charge[t]) * m.delta_t
    m.grid_transaction_constraint = Constraint(m.T, rule=grid_transaction_rule)

    def profit_rule(m, t):
        return m.profit[t] == m.grid_transaction[t] - m.degradation_cost[t]
    m.profit_constraint = Constraint(m.T, rule=profit_rule)

    # Objective
    def total_profit_rule(m):
        return sum(m.profit[t] for t in m.T)
    m.cost = Objective(rule=total_profit_rule, sense=maximize)

    return m