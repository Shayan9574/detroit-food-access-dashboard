"""Precomputed sensitivity sweeps (first nine sweeps, 59 solves)."""
NAMES_OPT = {"grocery_new": "New grocery store","grocery_upgrade": "Grocery upgrade","farmers_new": "New farmers market","farmers_upgrade": "Farmers market upgrade","mobile_market": "Mobile market"}
ADV_TYPE_KEYS = ["grocery_new", "grocery_upgrade", "mobile_market",
                 "farmers_new", "farmers_upgrade"]

# Per-parameter sweeps. Each "row" that is feasible carries the full
# five-type portfolio; infeasible / no-solution rows carry objective=None.
SENS_ADV = {
    "Budget (B)": {
        "label": "Budget", "unit": "$M", "baseline": 40,
        "description": (
            "The budget B caps total expenditure on the selected portfolio. The baseline "
            "$40M is the smallest budget for which full coverage with walking equity is "
            "feasible. The sweep tests two budgets below the baseline (to confirm "
            "infeasibility) and four above (to map the diminishing-returns frontier)."
        ),
        "rows": [
            {"value": 30, "label": "$30M", "status": "Infeasible", "objective": None},
            {"value": 35, "label": "$35M", "status": "Infeasible", "objective": None},
            {"value": 40, "label": "$40M", "status": "Optimal", "objective": 187.96, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 45, "label": "$45M", "status": "Optimal", "objective": 233.07, "gap": 0.08, "marginal": 9.02,
             "grocery_new": 4, "grocery_upgrade": 21, "mobile_market": 110, "farmers_new": 153, "farmers_upgrade": 25, "total": 313},
            {"value": 50, "label": "$50M", "status": "Optimal", "objective": 269.82, "gap": 0.19, "marginal": 7.35,
             "grocery_new": 4, "grocery_upgrade": 23, "mobile_market": 143, "farmers_new": 134, "farmers_upgrade": 26, "total": 330},
            {"value": 60, "label": "$60M", "status": "Optimal", "objective": 326.60, "gap": 0.27, "marginal": 5.68,
             "grocery_new": 4, "grocery_upgrade": 32, "mobile_market": 197, "farmers_new": 108, "farmers_upgrade": 26, "total": 367},
            {"value": 70, "label": "$70M", "status": "Optimal", "objective": 368.71, "gap": 0.23, "marginal": 4.21,
             "grocery_new": 4, "grocery_upgrade": 58, "mobile_market": 232, "farmers_new": 87, "farmers_upgrade": 30, "total": 411},
        ],
        "tradeoff": {
            "kind": "benefit_efficiency",
            "label_a": "Objective (benefit)",
            "label_b": "Marginal objective per $1M (efficiency)",
            "field_a": "objective", "field_b": "marginal",
            "story": ("As the budget rises the objective grows (benefit up) but the marginal "
                      "return per additional million dollars falls from $9.02 of objective at "
                      "$40M-$45M to $4.21 at $60M-$70M (efficiency down). The crossing marks the "
                      "natural diminishing-returns region."),
        },
        "findings": [
            "$40M is the smallest tested budget at which full coverage with walking equity is feasible; $30M and $35M are infeasible, so the minimum lies between $35M and $40M.",
            "Above the baseline the objective grows monotonically (187.96 to 368.71, +96%), while budget utilization stays above 99.7% at every feasible level, so the budget constraint binds tightly throughout.",
            "Marginal benefit per additional $1M declines from +9.02 objective units ($40M-$45M) to +4.21 ($60M-$70M): each extra dollar at $40M is worth more than twice each extra dollar at $70M.",
            "Composition shifts substantially with budget: mobile markets nearly triple (80 to 232), new farmers markets nearly halve (165 to 87), grocery upgrades triple (19 to 58), while new grocery stores stay at 4. Policy guidance must specify a budget context.",
        ],
    },

    "Walking threshold (d_walk)": {
        "label": "d_walk", "unit": "m", "baseline": 833,
        "description": (
            "The default maximum walking distance from a subpoint to a walking-eligible "
            "facility, before per-subpoint relaxation. Baseline 833 m (a 10-minute walk at "
            "5 km/h). The sweep spans a 7-minute walk (600 m) to a 14-minute walk (1200 m)."
        ),
        "rows": [
            {"value": 600, "label": "600 m", "status": "Infeasible", "objective": None, "aeff": 87903, "relaxed": 1305},
            {"value": 750, "label": "750 m", "status": "Time limit", "objective": 156.77, "gap": 1.09, "aeff": 88840, "relaxed": 922,
             "grocery_new": 4, "grocery_upgrade": 22, "mobile_market": 77, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 833, "label": "833 m", "status": "Optimal", "objective": 187.96, "gap": 0.50, "aeff": 89626, "relaxed": 763,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 1000, "label": "1000 m", "status": "Time limit", "objective": 245.23, "gap": 0.58, "aeff": 91751, "relaxed": 480,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 73, "farmers_new": 178, "farmers_upgrade": 27, "total": 302},
            {"value": 1200, "label": "1200 m", "status": "Optimal", "objective": 329.35, "gap": 0.15, "aeff": 94716, "relaxed": 279,
             "grocery_new": 4, "grocery_upgrade": 35, "mobile_market": 46, "farmers_new": 209, "farmers_upgrade": 24, "total": 318},
        ],
        "tradeoff": {
            "label_a": "Objective (benefit)", "label_b": "Mobile markets (driving-coverage reliance)",
            "field_a": "objective", "field_b": "mobile_market",
            "story": ("As the walking radius grows the achievable objective rises (benefit up) while the "
                      "model leans less on mobile markets for driving coverage (down): mobile markets and "
                      "walking radius are partial substitutes. The crossing marks the walking distance "
                      "where rising benefit overtakes the shrinking reliance on mobile coverage."),
        },
        "findings": [
            "This is the largest objective swing of any non-budget parameter: from 750 m to 1200 m the objective more than doubles (156.77 to 329.35, +110%).",
            "A 7-minute (600 m) walking standard is infeasible at $40M even with the largest relaxation count of any sweep value (1,305 subpoints). This is a real finding about Detroit's geography, not a modeling artifact.",
            "The 833 m (10-minute) walking standard is the single most consequential modeling choice in the framework.",
            "At 1200 m the mix shifts sharply (mobile 80 to 46, new farmers 165 to 209, grocery upgrades 19 to 35): mobile markets and walking radius are partial substitutes.",
        ],
    },

    "New farmers market cost": {
        "label": "farmers_new cost", "unit": "$K", "baseline": 100,
        "description": (
            "Unit cost of a new farmers market (baseline $100K), swept low/base/high at "
            "approximately +/-20% while all other type costs are held at baseline. This is "
            "the highest-count type in the baseline portfolio (165 of 294 facilities)."
        ),
        "rows": [
            {"value": 80, "label": "$80K", "status": "Optimal", "objective": 219.35,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 91, "farmers_new": 180, "farmers_upgrade": 25, "total": 319},
            {"value": 100, "label": "$100K", "status": "Optimal", "objective": 188.02,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 120, "label": "$120K", "status": "Optimal", "objective": 147.42,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 66, "farmers_new": 159, "farmers_upgrade": 26, "total": 275},
        ],
        "tradeoff_note": ("This is a high-sensitivity parameter, but it has no clean two-metric crossing: "
                          "as the unit cost rises the objective falls and the portfolio simply sparsens "
                          "(319 facilities at $80K to 275 at $120K) rather than trading one metric off "
                          "against another. The sensitivity itself is the finding; see the key findings below."),
        "findings": [
            "Objective swings from 219.35 at $80K to 147.42 at $120K (+17% / -22%), one of the two most cost-sensitive types in the model.",
            "The portfolio sparsens as cost rises: 319 facilities at $80K versus 275 at $120K, a swing of 44 facilities driven mostly by new farmers markets and mobile markets.",
            "New farmers markets are the cheapest walking-eligible new-build option, so their unit cost directly governs how cheaply the walking-equity constraint can be satisfied.",
            "Cities applying the framework should calibrate this cost carefully; partnerships that lower site-preparation expenses would tilt the portfolio meaningfully.",
        ],
    },

    "Mobile market cost": {
        "label": "mobile_market cost", "unit": "$K", "baseline": 200,
        "description": (
            "Unit cost of a mobile market (baseline $200K), swept low/base/high at "
            "approximately +/-20% with all other type costs held at baseline. Mobile markets "
            "are the second-highest-count type (80 of 294 facilities)."
        ),
        "rows": [
            {"value": 160, "label": "$160K", "status": "Optimal", "objective": 230.85,
             "grocery_new": 2, "grocery_upgrade": 19, "mobile_market": 134, "farmers_new": 127, "farmers_upgrade": 24, "total": 306},
            {"value": 200, "label": "$200K", "status": "Optimal", "objective": 188.02,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 240, "label": "$240K", "status": "Optimal", "objective": 162.20,
             "grocery_new": 4, "grocery_upgrade": 23, "mobile_market": 52, "farmers_new": 192, "farmers_upgrade": 27, "total": 298},
        ],
        "tradeoff": {
            "kind": "substitution",
            "label_a": "Mobile markets", "label_b": "New farmers markets",
            "field_a": "mobile_market", "field_b": "farmers_new",
            "story": ("As mobile cost rises, mobile deployments fall (134 to 52) and new farmers "
                      "markets rise (127 to 192) in a roughly one-for-one substitution. The "
                      "crossing marks the cost at which the two types are equally attractive."),
        },
        "findings": [
            "Objective swings from 230.85 at $160K to 162.20 at $240K (+23% / -14%), the other high-sensitivity unit cost alongside new farmers markets.",
            "Mobile markets and new farmers markets behave as near-perfect substitutes: at $160K mobile nearly doubles (80 to 134) and new farmers drop 38; at $240K mobile falls 28 and new farmers rise 27.",
            "The two dominate the portfolio because they are the most cost-effective among the types with abundant candidate-site supply (292 grid sites for new farmers; 324 grid+centroid sites for mobile).",
            "The choice between them is driven primarily by their relative cost.",
        ],
    },

    "No-vehicle ZIP cutoff": {
        "label": "No-vehicle cutoff", "unit": "", "baseline": 0.25,
        "description": (
            "ZIPs whose no-vehicle household rate exceeds this cutoff are car-light, and every "
            "subpoint in them must have walking access to a walking-eligible facility. Baseline "
            "0.25. The sweep tests a stricter 0.20 and looser 0.30 and 0.35."
        ),
        "rows": [
            {"value": 0.20, "label": "> 20%", "status": "No solution", "objective": None, "iwalk": 1651},
            {"value": 0.25, "label": "> 25%", "status": "Optimal", "objective": 188.02, "gap": 0.47, "iwalk": 727,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 0.30, "label": "> 30%", "status": "Optimal", "objective": 216.48, "gap": 0.33, "iwalk": 203,
             "grocery_new": 4, "grocery_upgrade": 10, "mobile_market": 109, "farmers_new": 125, "farmers_upgrade": 26, "total": 274},
            {"value": 0.35, "label": "> 35%", "status": "Optimal", "objective": 222.18, "gap": 0.47, "iwalk": 95,
             "grocery_new": 4, "grocery_upgrade": 8, "mobile_market": 117, "farmers_new": 113, "farmers_upgrade": 26, "total": 268},
        ],
        "tradeoff": {
            "kind": "equity_price",
            "label_a": "Objective (achievable benefit)",
            "label_b": "Walking-required subpoints (equity reach)",
            "field_a": "objective", "field_b": "iwalk",
            "story": ("Loosening the cutoff raises the achievable objective (fewer subpoints must "
                      "be walk-covered) but shrinks equity reach. The crossing is where extra "
                      "achievable benefit and equity coverage balance, the price of broad equity."),
        },
        "findings": [
            "At a 20% cutoff, 1,651 of 2,706 subpoints (61%) require walking access and no feasible solution was found within 30 minutes at $40M, a strong practical signal that broad equity needs more budget or looser thresholds.",
            "Each additional ~100 subpoints designated car-light costs about 5 objective units in the feasible regime; the relationship is roughly linear.",
            "Loosening the rule produces large mix shifts: grocery upgrades fall 19 to 8 (-58%), new farmers fall 165 to 113 (-31%), mobile markets rise 80 to 117 (+46%).",
            "Together with the weight and walking-threshold sweeps, this confirms that the walking-equity constraint is the dominant binding constraint.",
        ],
    },

    "Coverage target (theta)": {
        "label": "theta", "unit": "", "baseline": 1.00,
        "description": (
            "The minimum fraction of each subpoint's demand that must be served. Baseline "
            "1.00 (full coverage) plus walking access for car-light subpoints. The sweep "
            "tests five lower values to measure the equity-versus-impact tradeoff."
        ),
        "rows": [
            {"value": 0.75, "label": "0.75", "status": "Time limit", "objective": 215.81, "gap": 1.04,
             "grocery_new": 3, "grocery_upgrade": 18, "mobile_market": 94, "farmers_new": 148, "farmers_upgrade": 25, "total": 288},
            {"value": 0.80, "label": "0.80", "status": "Time limit", "objective": 209.21, "gap": 1.87,
             "grocery_new": 3, "grocery_upgrade": 18, "mobile_market": 88, "farmers_new": 159, "farmers_upgrade": 24, "total": 292},
            {"value": 0.85, "label": "0.85", "status": "Time limit", "objective": 205.58, "gap": 1.13,
             "grocery_new": 3, "grocery_upgrade": 19, "mobile_market": 88, "farmers_new": 158, "farmers_upgrade": 24, "total": 292},
            {"value": 0.90, "label": "0.90", "status": "Optimal", "objective": 201.34, "gap": 0.36,
             "grocery_new": 3, "grocery_upgrade": 19, "mobile_market": 89, "farmers_new": 156, "farmers_upgrade": 25, "total": 292},
            {"value": 0.95, "label": "0.95", "status": "Time limit", "objective": 193.86, "gap": 0.90,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 82, "farmers_new": 160, "farmers_upgrade": 26, "total": 292},
            {"value": 1.00, "label": "1.00", "status": "Optimal", "objective": 187.96, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
        ],
        "tradeoff": {
            "label_a": "Objective (achievable benefit)", "label_b": "Coverage guarantee (theta)",
            "field_a": "objective", "field_b": "value",
            "story": ("Raising the coverage guarantee theta serves more of every subpoint (equity up) but "
                      "lowers the achievable objective (benefit down). The crossing traces the equity-"
                      "versus-impact frontier: the coverage level where the guarantee and the achievable "
                      "benefit are in balance."),
        },
        "findings": [
            "Full coverage costs roughly 4% of achievable benefit relative to 95% coverage, the quantified price of the universal-coverage equity commitment.",
            "The plan structure is stable across theta (total facilities 288 to 294), with mild substitution between mobile markets and new farmers markets as theta relaxes.",
            "The coverage target is a policy lever rather than a technical parameter.",
        ],
    },

    "Objective weights (omega)": {
        "label": "weight vector", "unit": "", "baseline": "equal",
        "description": (
            "The objective combines three normalized outcomes (food access A, unhealthy-"
            "exposure reduction R, and cardiometabolic health burden Q) through weights "
            "summing to one. Baseline is equal (1/3 each). The sweep tests seven vectors "
            "spanning the corners and edges of the weight simplex."
        ),
        "rows": [
            {"value": "equal", "label": "equal", "status": "Optimal", "objective": 187.96, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": "A_focus", "label": "A_focus", "status": "Time limit", "objective": 181.95, "gap": 0.85,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 164, "farmers_upgrade": 26, "total": 293},
            {"value": "R_focus", "label": "R_focus", "status": "Time limit", "objective": 196.11, "gap": 1.77,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 81, "farmers_new": 162, "farmers_upgrade": 26, "total": 292},
            {"value": "Q_focus", "label": "Q_focus", "status": "Optimal", "objective": 183.13, "gap": 0.22,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 81, "farmers_new": 163, "farmers_upgrade": 26, "total": 293},
            {"value": "A+Q", "label": "A+Q", "status": "Time limit", "objective": 173.65, "gap": 1.05,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 82, "farmers_new": 161, "farmers_upgrade": 26, "total": 292},
            {"value": "A+R", "label": "A+R", "status": "Optimal", "objective": 194.84, "gap": 0.43,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": "R+Q", "label": "R+Q", "status": "Optimal", "objective": 195.13, "gap": 0.28,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 81, "farmers_new": 163, "farmers_upgrade": 26, "total": 293},
        ],
        "findings": [
            "The recommended portfolio is essentially weight-invariant: facility counts vary by at most +/-2 of any type across the entire weight simplex.",
            "Two structural reasons: the coverage and walking-equity constraints dominate at the $40M budget, and the health-burden outcome Q is the cardiometabolic coefficient times the food-access improvement, so Q moves in lockstep with A.",
            "The objective range (173.65 to 196.11, about +/-6%) is partly a normalization artifact rather than a real policy effect.",
            "Prioritizing cardiometabolic outcomes over food access would not meaningfully change the recommended plan.",
        ],
    },

    "Driving threshold (d_drive)": {
        "label": "d_drive", "unit": "m", "baseline": 5000,
        "description": (
            "The maximum driving distance for mobile-market service. Baseline 5000 m (a "
            "10-minute drive at 30 km/h). The sweep tests +/-20% around the baseline."
        ),
        "rows": [
            {"value": 4000, "label": "4000 m", "status": "Time limit", "objective": 177.86, "gap": 1.24, "aeff": 62269,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 166, "farmers_upgrade": 26, "total": 294},
            {"value": 4500, "label": "4500 m", "status": "Time limit", "objective": 184.25, "gap": 0.53, "aeff": 75566,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 25, "total": 293},
            {"value": 5000, "label": "5000 m", "status": "Optimal", "objective": 187.96, "gap": 0.50, "aeff": 89626,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 5500, "label": "5500 m", "status": "Optimal", "objective": 191.78, "gap": 0.30, "aeff": 104720,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 166, "farmers_upgrade": 26, "total": 295},
            {"value": 6000, "label": "6000 m", "status": "Optimal", "objective": 195.25, "gap": 0.26, "aeff": 120901,
             "grocery_new": 3, "grocery_upgrade": 19, "mobile_market": 84, "farmers_new": 166, "farmers_upgrade": 26, "total": 298},
        ],
        "tradeoff_note": ("No meaningful trade-off: across the tested range the objective moves less than "
                          "10% and the portfolio is essentially invariant (all type counts within +/-4 "
                          "facilities). Driving access is plentiful in Detroit, so the driving radius is "
                          "not a binding scarce resource."),
        "findings": [
            "Objective ranges 177.86 to 195.25 (under 10%) across a 50% change in the parameter, a mild sensitivity, an order of magnitude smaller than the walking threshold.",
            "The portfolio is essentially invariant (all type counts within +/-4 facilities); only at 6000 m does the model drop one new grocery for four more mobile markets.",
            "The contrast with the walking threshold is informative: walking equity is structurally hard in Detroit, driving access is plentiful, so walking-eligible facilities, not mobile markets, are the binding scarce resource.",
            "Any value in [4500 m, 5500 m] produces effectively the same plan, so the 5000 m baseline is easy to defend.",
        ],
    },

    "Cost penalty (lambda)": {
        "label": "lambda", "unit": "", "baseline": 0.0,
        "description": (
            "A penalty term -lambda * sum(C_jk / B) * x_jk added to the objective to test "
            "whether the model would spend less than the full budget if encouraged to. "
            "Baseline lambda = 0 (no penalty)."
        ),
        "rows": [
            {"value": 0.0, "label": "0.0", "status": "Optimal", "objective": 188.02, "gap": 0.47, "budget_used": 99.93,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 0.5, "label": "0.5", "status": "Time limit", "objective": 186.58, "gap": 0.97, "budget_used": 99.95,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
            {"value": 1.0, "label": "1.0", "status": "Time limit", "objective": 186.84, "gap": 0.54, "budget_used": 99.90,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 2.0, "label": "2.0", "status": "Time limit", "objective": 185.14, "gap": 0.94, "budget_used": 99.95,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
            {"value": 3.0, "label": "3.0", "status": "Time limit", "objective": 183.77, "gap": 1.14, "budget_used": 99.96,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
            {"value": 5.0, "label": "5.0", "status": "Time limit", "objective": 181.97, "gap": 1.05, "budget_used": 99.86,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
        ],
        "findings": [
            "At every lambda tested the model still uses more than 99.85% of the budget: the cost penalty has essentially no effect on spending.",
            "The ~6-unit objective drop from lambda 0 to 5 is approximately equal to the penalty term itself (at lambda 5 the penalty is about 4.99 units), so it is a constant offset, not a change of plan.",
            "The penalty is ineffective because the coverage and walking-equity constraints require a minimum of about 294 facilities, and the budget is already a hard upper bound; dropping facilities to save money would violate the constraints.",
            "This null finding supports lambda = 0 in the baseline configuration.",
        ],
    },

    "Income-cost elasticity (gamma)": {
        "label": "gamma", "unit": "", "baseline": 0.3,
        "description": (
            "Controls how site costs scale with local median income: "
            "C = C_base * (1 + gamma * (Inc − Median) / Median). Baseline gamma = 0.3. "
            "The sweep tests gamma = 0 (no adjustment) up to gamma = 0.7 (strong elasticity)."
        ),
        "rows": [
            {"value": 0.0, "label": "0.0", "status": "Optimal", "objective": 190.18, "gap": 0.47,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 79, "farmers_new": 166, "farmers_upgrade": 26, "total": 295},
            {"value": 0.1, "label": "0.1", "status": "Time limit", "objective": 187.58, "gap": 1.24,
             "grocery_new": 4, "grocery_upgrade": 21, "mobile_market": 79, "farmers_new": 164, "farmers_upgrade": 26, "total": 294},
            {"value": 0.3, "label": "0.3", "status": "Optimal", "objective": 188.02, "gap": 0.47,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 0.5, "label": "0.5", "status": "Time limit", "objective": 187.53, "gap": 0.60,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 166, "farmers_upgrade": 26, "total": 295},
            {"value": 0.7, "label": "0.7", "status": "Optimal", "objective": 187.86, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 167, "farmers_upgrade": 26, "total": 296},
        ],
        "findings": [
            "Objective varies only 187.5 to 190.2 across the full gamma range, a 1.4% swing, the smallest sensitivity of any parameter tested.",
            "Maximum variation across the grid is +/-2 facilities of any type; gamma is the most robust parameter in the entire model.",
            "Detroit ZIP incomes cluster near the median of the 32 ZIP-level median incomes ($36,932), so even at gamma = 0.7 the cost multiplier rarely exceeds +/-25%, and the tightly binding budget means the optimizer just fits the cheapest feasible configuration.",
            "Income-based cost adjustment is a refinement, not a load-bearing assumption; it can be reported at baseline 0.3 without lengthy justification.",
        ],
    },
}

# Display order: most consequential first (matches the tornado tiers)
SENS_ADV_ORDER = [
    "Walking threshold (d_walk)",
    "Budget (B)",
    "New farmers market cost",
    "Mobile market cost",
    "No-vehicle ZIP cutoff",
    "Coverage target (theta)",
    "Objective weights (omega)",
    "Driving threshold (d_drive)",
    "Cost penalty (lambda)",
    "Income-cost elasticity (gamma)",
]

# Tornado ranking transcribed from the report's cross-sweep table (objective
# swing %, all 13 parameters incl. the three low-sensitivity cost sweeps that
# the report reports as objective-only).
TORNADO_ADV = [
    {"param": "Walking threshold (d_walk)", "swing": 110.0, "tier": 1, "note": "mobile -43%, farmers +27%"},
    {"param": "Budget B",                   "swing": 96.0,  "tier": 1, "note": "mobile +190%, farmers -47%"},
    {"param": "Mobile market cost",         "swing": 23.0,  "tier": 2, "note": "1:1 substitution with farmers"},
    {"param": "New farmers market cost",    "swing": 22.0,  "tier": 2, "note": "+/-25 facilities"},
    {"param": "No-vehicle cutoff",          "swing": 18.0,  "tier": 2, "note": "farmers -31%, mobile +46%"},
    {"param": "Coverage target theta",      "swing": 15.0,  "tier": 3, "note": "288 to 294 facilities"},
    {"param": "Objective weights omega",    "swing": 12.0,  "tier": 3, "note": "+/-2 facilities (normalization)"},
    {"param": "Driving threshold d_drive",  "swing": 10.0,  "tier": 3, "note": "+/-4 facilities"},
    {"param": "Grocery upgrade cost",       "swing": 4.0,   "tier": 4, "note": "minor"},
    {"param": "New grocery cost",           "swing": 3.0,   "tier": 4, "note": "-2 grocery at high cost"},
    {"param": "Cost penalty lambda",        "swing": 3.0,   "tier": 4, "note": "penalty offset only"},
    {"param": "Income-cost elasticity gamma","swing": 1.4,  "tier": 4, "note": "+/-2 facilities"},
    {"param": "Farmers upgrade cost",       "swing": 1.0,   "tier": 4, "note": "supply-capped"},
]
TORNADO_TIER_COLOR = {1: "#7F1D1D", 2: "#B45309", 3: "#1A2B47", 4: "#6B7280"}


def _sens_feasible(block):
    """Rows with a numeric objective (feasible / time-limited)."""
    return [r for r in block["rows"] if r.get("objective") is not None]


def _sens_infeasible_note(block):
    bad = [r["label"] for r in block["rows"] if r.get("objective") is None]
    return bad


def _norm01(vals):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def _first_crossing(xs, ya, yb):
    for i in range(len(xs) - 1):
        d1 = ya[i] - yb[i]
        d2 = ya[i + 1] - yb[i + 1]
        if d1 == 0:
            return xs[i]
        if d1 * d2 < 0:
            t = d1 / (d1 - d2)
            return xs[i] + t * (xs[i + 1] - xs[i])
    if ya[-1] == yb[-1]:
        return xs[-1]
    return None


def _intersection_xy(xs, ya, yb):
    """First intersection of two piecewise-linear curves over numeric xs.
    Returns (x_int, y_int) interpolated on both x and the y level, or None."""
    for i in range(len(xs) - 1):
        d1 = ya[i] - yb[i]
        d2 = ya[i + 1] - yb[i + 1]
        if d1 == 0:
            return xs[i], ya[i]
        if d1 * d2 < 0:
            t = d1 / (d1 - d2)              # fraction of the segment to the crossing
            x_int = xs[i] + t * (xs[i + 1] - xs[i])
            y_int = ya[i] + t * (ya[i + 1] - ya[i])
            return x_int, y_int
    if ya[-1] == yb[-1]:
        return xs[-1], ya[-1]
    return None


def _fmt_cross(x, unit, label):
    """Format a crossing x-value in the parameter's real units."""
    if unit == "$M":
        return f"${x:,.1f}M"
    if unit == "$K":
        return f"${x:,.0f}K"
    if unit == "m":
        return f"{x:,.0f} m"
    if label == "No-vehicle cutoff":
        return f"{x * 100:.0f}%"
    return f"{x:.2f}"

