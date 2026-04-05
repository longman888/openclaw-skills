#!/usr/bin/env python3
"""
Strategy Evolution Engine — genetic algorithm for strategy optimization.
Based on evolutionary computation principles.

Evolution cycle:
1. Generate population of strategy variants
2. Backtest each variant
3. Score by fitness function
4. Select top performers (elitism)
5. Mutate survivors
6. Repeat
"""

import os
import json
import uuid
import random
import logging
import math
import copy
import platform
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("evolution")


# ─── Paths ──────────────────────────────────────────────────────────────────

# ─── Paths ───────────────────────────────────────────────────────────────────
# OpenClaw workspace override (set OPENCLAW_STRATEGIES_DIR env var to customize)
_STRATEGIES_ROOT = Path(os.environ.get(
    "OPENCLAW_STRATEGIES_DIR",
    Path.home() / ".claude" / "strategies" if platform.system() != "Windows"
    else r"E:\.openclaw\strategies"
))
STRATEGIES_DIR = _STRATEGIES_ROOT
POPULATION_DIR = STRATEGIES_DIR / "populations"
GENEALOGIES_DIR = STRATEGIES_DIR / "genealogies"


# ─── Strategy Model ──────────────────────────────────────────────────────────

@dataclass
class Strategy:
    id: str
    name: str
    version: int
    strategy_type: str           # "trend_following", "mean_reversion", etc.
    params: dict
    parent_id: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ─── Fitness ────────────────────────────────────────────────────────────────

def fitness_score(metrics: dict) -> float:
    """
    Multi-dimensional fitness scoring.
    Combines return, risk-adjusted return, drawdown, win rate.
    All inputs normalized to 0-1 range.
    """
    # Normalize return (0-1, cap at 100%)
    ret = min(metrics.get("total_return", 0), 1.0)
    # Normalize Sharpe (0-1, cap at 3.0)
    sharpe = min(metrics.get("sharpe_ratio", 0), 3.0) / 3.0
    # Drawdown: more negative = worse, 0 = best
    dd = min(abs(metrics.get("max_drawdown", 0)), 0.5) / 0.5
    dd_score = 1.0 - dd  # invert: -0.1 → 0.8, -0.3 → 0.4, -0.5 → 0.0
    # Win rate: 0-1
    win = metrics.get("win_rate", 0.5)
    # Trade count: penalize too few (need sample)
    count = min(metrics.get("trade_count", 0), 100) / 100.0
    # Consistency: 1 - CV (coefficient of variation)
    equity = metrics.get("equity_curve", [1.0])
    if len(equity) > 1:
        returns = [(equity[i] - equity[i-1]) / equity[i-1] for i in range(1, len(equity))]
        mean_r = sum(returns) / len(returns) if returns else 0
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns)) if returns else 1e-9
        consistency = 1.0 - min(std_r / abs(mean_r) if mean_r else 1.0, 1.0)
    else:
        consistency = 0.5

    score = (
        0.25 * ret +
        0.25 * sharpe +
        0.20 * dd_score +
        0.15 * win +
        0.10 * count +
        0.05 * consistency
    )
    return round(score, 4)


# ─── Mutation ────────────────────────────────────────────────────────────────

MUTATION_PROBS = {
    "param_tweak": 0.40,
    "add_rule": 0.15,
    "remove_rule": 0.10,
    "swap_indicator": 0.10,
    "combine": 0.15,
    "restart": 0.10,
}

PARAM_RANGES = {
    "fast_ma": (3, 20),
    "slow_ma": (10, 60),
    "macd_fast": (8, 16),
    "macd_slow": (20, 34),
    "macd_signal": (5, 15),
    "rsi_period": (7, 21),
    "rsi_oversold": (20, 40),
    "rsi_overbought": (60, 80),
    "bb_period": (10, 30),
    "bb_std": (1.5, 3.0),
    "atr_period": (7, 21),
    "stop_loss_pct": (0.02, 0.10),
    "take_profit_pct": (0.05, 0.25),
    "position_size_pct": (0.05, 0.30),
    "max_positions": (1, 10),
}

RULE_FLAGS = [
    "trend_filter", "volume_filter", "volatility_filter",
    "news_filter", "sentiment_filter", "sector_filter"
]


def mutate_param(value: float, param_key: str) -> float:
    """Mutate a numeric parameter by ±10-30%."""
    lo, hi = PARAM_RANGES.get(param_key, (0.5, 2.0))
    factor = random.uniform(0.7, 1.3)
    new_val = value * factor
    return max(lo, min(hi, new_val))


def mutate(strategy: Strategy, population: list[Strategy]) -> Strategy:
    """Apply random mutation to a strategy."""
    op = random.choices(
        list(MUTATION_PROBS.keys()),
        weights=list(MUTATION_PROBS.values())
    )[0]

    new_params = copy.deepcopy(strategy.params)

    if op == "param_tweak":
        key = random.choice(list(new_params.keys()))
        if isinstance(new_params[key], (int, float)):
            new_params[key] = round(mutate_param(new_params[key], key), 4)

    elif op == "add_rule":
        available = [r for r in RULE_FLAGS if r not in new_params]
        if available:
            key = random.choice(available)
            new_params[key] = random.choice([True, False])

    elif op == "remove_rule":
        removable = [r for r in RULE_FLAGS if r in new_params and new_params[r] == True]
        if removable:
            key = random.choice(removable)
            del new_params[key]

    elif op == "swap_indicator":
        # Replace one indicator with equivalent
        swaps = {
            "rsi_period": ("rsi_period", lambda v: v + random.randint(-2, 2)),
            "fast_ma": ("fast_ma", lambda v: v + random.randint(-2, 2)),
            "slow_ma": ("slow_ma", lambda v: v + random.randint(-5, 5)),
        }
        key = random.choice(list(swaps.keys()))
        if key in new_params:
            _, fn = swaps[key]
            new_params[key] = round(max(1, fn(new_params[key])))

    elif op == "combine":
        # Take some params from a top performer
        if len(population) >= 3:
            donor = random.choice(population[:5])
            for k, v in random.sample(list(donor.params.items()), k=max(1, len(donor.params) // 3)):
                if isinstance(v, (int, float)):
                    new_params[k] = round(random.uniform(min(v, new_params.get(k, v)), max(v, new_params.get(k, v))), 4)

    elif op == "restart":
        # Fresh random params
        for key, (lo, hi) in PARAM_RANGES.items():
            new_params[key] = round(random.uniform(lo, hi), 4)
        # Random rule flags
        for rule in RULE_FLAGS:
            new_params[rule] = random.random() < 0.3

    new_id = str(uuid.uuid4())[:12]
    return Strategy(
        id=new_id,
        name=f"{strategy.name}_m{strategy.version+1}",
        version=strategy.version + 1,
        strategy_type=strategy.strategy_type,
        params=new_params,
        parent_id=strategy.id,
        created_at=datetime.now().isoformat()
    )


# ─── Backtest (Placeholder) ─────────────────────────────────────────────────

def run_backtest(strategy: Strategy, symbol: str = "AAPL", period: str = "1y") -> dict:
    """
    Run backtest on strategy.
    In production: use actual historical data and trading simulation.
    Here: generate synthetic results based on strategy params.
    """
    # Synthetic metrics based on strategy parameters
    # (This is a placeholder; real implementation connects to data API)
    random.seed(strategy.id)  # reproducible

    # Rough correlation between params and metrics
    fast = strategy.params.get("fast_ma", 10)
    slow = strategy.params.get("slow_ma", 20)
    stop = strategy.params.get("stop_loss_pct", 0.05)

    # Simulate performance
    base_return = random.uniform(-0.2, 0.5)
    # Trend following with reasonable MA combo does better
    if slow / fast > 2 and slow / fast < 4:
        base_return *= 1.2
    # Stop loss discipline helps
    if stop < 0.07:
        base_return *= 1.1

    sharpe = base_return / max(random.uniform(0.05, 0.3), 0.01)
    max_dd = -abs(random.uniform(0.05, 0.3) * (1.5 if stop > 0.07 else 1.0))
    win_rate = random.uniform(0.4, 0.7)
    trade_count = int(random.uniform(10, 50))

    # Generate equity curve
    equity = [1.0]
    for i in range(trade_count):
        ret = random.gauss(base_return / trade_count, 0.02)
        if random.random() < win_rate:
            ret = abs(ret) * 1.5
        else:
            ret = -abs(ret)
        equity.append(equity[-1] * (1 + ret))

    metrics = {
        "total_return": round((equity[-1] - 1.0) * 100, 2),
        "annualized_return": round((equity[-1] ** (252/trade_count) - 1) * 100, 2) if trade_count > 0 else 0,
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_dd, 4),
        "win_rate": round(win_rate, 3),
        "trade_count": trade_count,
        "equity_curve": [round(e, 4) for e in equity],
    }

    return {
        "strategy_id": strategy.id,
        "symbol": symbol,
        "period": period,
        "metrics": metrics,
        "fitness": fitness_score(metrics),
        "timestamp": datetime.now().isoformat()
    }


# ─── Evolution ─────────────────────────────────────────────────────────────

class EvolutionEngine:
    def __init__(
        self,
        strategy_type: str = "trend_following",
        population_size: int = 20,
        elite_size: int = 3,
        generations: int = 50
    ):
        self.strategy_type = strategy_type
        self.population_size = population_size
        self.elite_size = elite_size
        self.generations = generations
        self.population: list[Strategy] = []
        self.generation_results: list[dict] = []
        STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
        POPULATION_DIR.mkdir(parents=True, exist_ok=True)
        GENEALOGIES_DIR.mkdir(parents=True, exist_ok=True)

    def initialize_population(self):
        """Create initial random population."""
        self.population = []
        base_params = {
            "fast_ma": 10, "slow_ma": 20,
            "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
            "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
            "bb_period": 20, "bb_std": 2.0,
            "atr_period": 14,
            "stop_loss_pct": 0.05, "take_profit_pct": 0.15,
            "position_size_pct": 0.20, "max_positions": 5,
            "trend_filter": False, "volume_filter": False,
        }
        for i in range(self.population_size):
            params = {k: mutate_param(v, k) for k, v in base_params.items()}
            s = Strategy(
                id=str(uuid.uuid4())[:12],
                name=f"{self.strategy_type}_v{i+1}",
                version=1,
                strategy_type=self.strategy_type,
                params=params
            )
            self.population.append(s)
        log.info(f"Initialized population: {len(self.population)} strategies")

    def evolve_generation(self, gen: int, symbol: str = "AAPL") -> list[dict]:
        """Run one generation of evolution."""
        log.info(f"=== Generation {gen} ===")

        # Backtest all
        results = []
        for s in self.population:
            r = run_backtest(s, symbol)
            r["fitness"] = fitness_score(r["metrics"])
            results.append((s, r))

        # Sort by fitness
        results.sort(key=lambda x: -x[1]["fitness"])
        scored = results

        log.info(f"Best fitness: {scored[0][1]['fitness']:.4f} | "
                 f"worst: {scored[-1][1]['fitness']:.4f}")

        # Save generation
        gen_path = POPULATION_DIR / f"gen_{gen:03d}.json"
        gen_data = {
            "generation": gen,
            "results": [{"strategy": s.to_dict(), "metrics": r["metrics"], "fitness": r["fitness"]}
                        for s, r in scored]
        }
        gen_path.write_text(json.dumps(gen_data, indent=2))

        # Save genealogy for top performers
        for s, r in scored[:self.elite_size]:
            self._save_genealogy(s, r, gen)

        # Log best strategy
        best_s, best_r = scored[0]
        log.info(f"Best: {best_s.name} | fitness={best_r['fitness']:.4f} | "
                 f"return={best_r['metrics']['total_return']:.2f}% | "
                 f"sharpe={best_r['metrics']['sharpe_ratio']:.2f}")

        # Elite selection
        self.population = [s for s, _ in scored[:self.elite_size]]

        # Mutate survivors to refill population
        while len(self.population) < self.population_size:
            parent = random.choice(self.population[:self.elite_size])
            mutated = mutate(parent, self.population)
            self.population.append(mutated)

        self.generation_results.append(scored)
        return scored

    def _save_genealogy(self, strategy: Strategy, result: dict, gen: int):
        """Save strategy genealogy."""
        path = GENEALOGIES_DIR / f"{strategy.id}.json"
        data = {
            "strategy_id": strategy.id,
            "lineage": [{"id": strategy.id, "name": strategy.name,
                        "fitness": result["fitness"], "gen": gen}],
            "mutations": [],
            "final_metrics": result["metrics"]
        }
        path.write_text(json.dumps(data, indent=2))

    def run(self, symbol: str = "AAPL") -> Strategy:
        """Run full evolution."""
        if not self.population:
            self.initialize_population()

        for gen in range(1, self.generations + 1):
            self.evolve_generation(gen, symbol)

        # Return best strategy
        best = max(self.generation_results[-1], key=lambda x: x[1]["fitness"])
        log.info(f"\n=== EVOLUTION COMPLETE ===")
        log.info(f"Best strategy: {best[0].name}")
        log.info(f"Final fitness: {best[1]['fitness']:.4f}")
        log.info(f"Total return: {best[1]['metrics']['total_return']:.2f}%")
        log.info(f"Sharpe: {best[1]['metrics']['sharpe_ratio']:.2f}")
        log.info(f"Max DD: {best[1]['metrics']['max_drawdown']*100:.1f}%")
        log.info(f"Win rate: {best[1]['metrics']['win_rate']*100:.0f}%")
        return best[0]


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Strategy Evolution Engine")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Run evolution")
    p_run.add_argument("--type", default="trend_following")
    p_run.add_argument("--generations", type=int, default=20)
    p_run.add_argument("--population", type=int, default=20)
    p_run.add_argument("--symbol", default="AAPL")

    p_mutate = sub.add_parser("mutate", help="Mutate a strategy from JSON")
    p_mutate.add_argument("file", help="JSON file with strategy")

    args = parser.parse_args()

    if args.cmd == "run":
        eng = EvolutionEngine(
            strategy_type=args.type,
            population_size=args.population,
            generations=args.generations
        )
        best = eng.run(args.symbol)
        print(f"\nBest strategy:\n{json.dumps(best.to_dict(), indent=2)}")

    elif args.cmd == "mutate":
        data = json.loads(Path(args.file).read_text())
        s = Strategy(**data)
        mutated = mutate(s, [s])
        print(json.dumps(mutated.to_dict(), indent=2))

    else:
        parser.print_help()
