# ────────── CONFIG ──────────
CFG = {
    # ── Demography & basic macro variables ─────────────────────────────
    "mass_growth":   0.0015,   # monthly population growth of non-elites
    "elite_growth":  0.0010,   #   »   growth of elite cohort
    "infra_decay":   0.005,    # natural wear-and-tear on infrastructure
    "sec_decay":     0.005,    # peacetime drift in security capacity
    "tax_rate":      0.20,     # flat share of output captured by the state
    "vote_interval": 6,         # time between institution change votes

    # ── Professional army hiring policy ───────────────────────────────
    "min_ratio":     0.002,    # lower bound for pros : population
    "max_ratio":     0.01,     # upper bound                 »
    "hire_limit":    0.0002,   # max change in pro troops (± % of pop/month)
    "inertia_expand":0.10,     # speed for *raising* target ratio
    "inertia_contract":0.03,   # speed for *lowering* target ratio
    "soldier_cost":  1.5,      # payroll multiplier for each professional
    "conscript_cost":0.7,      #             »         for each conscript

    # ── Conscript draft logic ─────────────────────────────────────────
    "base_draft":    0.05,     # worst-case draft share when EI = 0

    # ── External‐invasion parameters ──────────────────────────────────
    "base_invade":   0.0002,   # floor probability of an invasion / month
    "safe_ratio":    0.013,    # pro-troop ratio that almost eliminates risk
    "invade_k":      20,       # steepness of risk curve when under-armed
    "min_enemy_strength":0.5,  # enemy force scaling (0.5–1.3× of ours)
    "max_enemy_strength":1.3,

    # ── Institution-updating (voting) ─────────────────────────────────
    "vote_step":     0.02,     # max Δ EI/PI after each 6-month election

    # ── Unrest & political violence ───────────────────────────────────
    "unrest_adjust": 0.001,    # speed at which grievance → unrest
    "unrest_output_penalty":0.05, # output loss when unrest > 0.4
    "protest_base":  0.05,     # base chance protests ignite when unrest high
    "civil_war_threshold":0.8, # unused (legacy) – threshold for auto-rebellion
    "coup_probability":0.05,   # baseline chance officers plot a coup each month

    # ── Combat effectiveness ──────────────────────────────────────────
    "equip_weight":  0.01,      # bonus from equipment/security spending

    # ── Development targets (long-run desired levels) ────────────────
    "targets": {
        "tech":  3.0,          # target technology index
        "infra": 2.5,          # target infrastructure stock
        "pc":    2.5           # target production capital
    },
    "alloc_floor":  0.05,      # min % of the budget any line item can get

    # ── Repression spending effectiveness ─────────────────────────────
    "repression_effectiveness":0.15, # unrest reduction per $ on repression
    "repression_cost_fraction":0.20, # share of *security* budget used to repress

    # ── Natural-disaster model ────────────────────────────────────────
    "disaster_base":         0.03,  # baseline monthly disaster probability
    "disaster_infra_coeff":  0.01,  # ↑ risk when infra < target
    "disaster_unrest_coeff": 0.01,  # ↑ risk when unrest is high

    # ── UI / runtime convenience ──────────────────────────────────────
    "sleep": 0                # seconds to sleep between months (0 = fastest)
}
