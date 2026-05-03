from __future__ import annotations
import math


def cobb_douglas(mass_pop: float, elite_pop: float, EI: float,
                 pc: float, infra: float, tech: float) -> float:
    labour = mass_pop * EI + elite_pop
    capital = pc + infra
    return tech * (labour ** 0.67) * (capital ** 0.33)


def compute_sector_productivity(EI: float, tech: float, infra_ratio: float) -> dict[str, float]:
    return {
        "agriculture": max(0.1, infra_ratio * 0.8 + 0.2),
        "industry":    max(0.1, (tech / 3.0) * 0.6 + 0.4),
        "services":    max(0.1, EI * 0.7 + 0.3),
    }


def sector_tfp(EI: float, tech: float, infra_ratio: float,
               weights: dict[str, float]) -> float:
    prod = compute_sector_productivity(EI, tech, infra_ratio)
    tfp = 1.0
    total_w = sum(weights.values()) or 1.0
    for sector, w in weights.items():
        tfp *= prod.get(sector, 1.0) ** (w / total_w)
    return max(0.01, tfp)


def compute_gini(mass_pop: float, elite_pop: float,
                 mass_income: float, elite_income: float) -> float:
    n1, n2 = mass_pop, elite_pop
    y1 = mass_income / (n1 + 1e-9)
    y2 = elite_income / (n2 + 1e-9)
    total_pop = n1 + n2
    total_income = mass_income + elite_income + 1e-9
    s1 = n1 / total_pop
    s2 = n2 / total_pop
    mu = total_income / total_pop
    gini = (s1 * s2 * abs(y1 - y2)) / (mu + 1e-9)
    return max(0.0, min(1.0, gini))


def resource_rent(output: float, rent_share: float, EI: float) -> tuple[float, float]:
    if rent_share <= 0:
        return 0.0, 0.0
    rent = output * rent_share
    dutch_disease_drag = rent_share * 0.3 * (1 - EI)
    return rent, dutch_disease_drag
