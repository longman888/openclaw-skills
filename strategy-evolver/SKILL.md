---
name: strategy-evolver
description: |
  Self-evolving strategy system — learns from trade outcomes, refines rules, tracks strategy performance.
  Triggers when: (1) user asks to review strategy performance;
  (2) generating new strategy variants;
  (3) learning from trade outcomes (win/loss analysis);
  (4) mutating and testing strategy parameters.
  Provides: evolution engine, backtest comparison, parameter mutation, fitness scoring.
---

# Strategy Evolver

## Core Concept

Strategies evolve through a Darwinian cycle:

```
生成 → 回测 → 评估 → 选择 → 变异 → 生成 → ...
         ↑__________________________________|
```

Each generation produces strategy variants, the best survive and mutate.

## Evolution Loop

```python
class StrategyEvolver:
    def evolve(self, generation: int) -> list[Strategy]:
        # 1. Generate variants
        variants = self.mutate(self.population)

        # 2. Backtest all
        results = [self.backtest(v) for v in variants]

        # 3. Score by fitness
        scored = [(v, self.fitness(r)) for v, r in zip(variants, results)]

        # 4. Select top performers
        self.population = [v for v, _ in sorted(scored, key=lambda x: -x[1])[:self.elite_size]]

        # 5. Log generation
        self.log_generation(generation, scored)

        return self.population
```

## Fitness Function

Each strategy variant is scored on multiple dimensions:

| Metric | Weight | Description |
|--------|--------|-------------|
| Total Return | 0.25 | Overall return over backtest period |
| Sharpe Ratio | 0.25 | Risk-adjusted return |
| Max Drawdown | 0.20 | Largest peak-to-trough (-pentalty) |
| Win Rate | 0.15 | Percentage of profitable trades |
| Trade Count | 0.10 | Sufficient sample size |
| Consistency | 0.05 | Low variance of returns |

```
fitness = 0.25*ret_norm + 0.25*sharpe_norm + 0.20*(1+dd_norm)
         + 0.15*win_rate + 0.10*trade_norm + 0.05*consistency
```

## Strategy Representation

Strategies are encoded as parameter sets:

```python
@dataclass
class Strategy:
    id: str
    name: str
    version: int
    params: dict
    parent_id: str = ""  # for lineage tracking

    # Example: trend_following with mutated params
    params = {
        "fast_ma": 5,
        "slow_ma": 20,
        "macd_signal_period": 9,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "stop_loss_pct": 0.05,
        "position_size_pct": 0.20,
        "max_positions": 5,
        "trend_filter": True,   # NEW in this variant
        "volume_filter": True,  # NEW in this variant
    }
```

## Mutation Operations

Strategies mutate through these operations:

| Operation | Description | Probability |
|-----------|-------------|-------------|
| **Parameter tweak** | ±5-20% on numeric parameter | 40% |
| **Add rule** | Add a new condition (e.g., volume filter) | 15% |
| **Remove rule** | Remove a rarely-true condition | 10% |
| **Swap indicator** | Replace RSI with KDJ for same role | 10% |
| **Combine** | Combine rules from two top performers | 15% |
| **Restart** | Random new strategy | 10% |

```python
def mutate(strategy: Strategy) -> Strategy:
    op = weighted_choice(MUTATION_OPS, PROBABILITIES)
    new_params = dict(strategy.params)

    if op == "param_tweak":
        key = random.choice(list(new_params.keys()))
        if isinstance(new_params[key], (int, float)):
            new_params[key] *= random.uniform(0.8, 1.2)

    elif op == "add_rule":
        new_params["volume_filter"] = True  # always add volume filter variant

    elif op == "combine":
        other = random.choice(population[:10])
        for k, v in random.choice(list(other.params.items())):
            if random.random() < 0.3:
                new_params[k] = v

    return Strategy(
        id=gen_id(),
        name=f"{strategy.name}_v{strategy.version+1}",
        version=strategy.version + 1,
        params=new_params,
        parent_id=strategy.id
    )
```

## Backtest Engine

```python
def backtest(strategy: Strategy, data: KLineData, start: date, end: date) -> BacktestResult:
    """
    Run backtest on historical data.
    Returns: trades, equity_curve, metrics
    """
    signals = generate_signals(strategy, data)
    trades = execute_trades(signals, data, strategy.params)
    equity = compute_equity(trades, data)
    metrics = compute_metrics(equity, trades)
    return BacktestResult(trades=trades, equity=equity, metrics=metrics)
```

## Evolution Configuration

```json
{
  "evolution": {
    "population_size": 20,
    "elite_size": 3,
    "generations": 50,
    "mutation_rate": 0.15,
    "crossover_rate": 0.20,
    "backtest": {
      "period": "2024-01-01 to 2026-04-01",
      "initial_capital": 1000000,
      "commission": 0.0003,
      "slippage": 0.001
    },
    "fitness": {
      "return_weight": 0.25,
      "sharpe_weight": 0.25,
      "drawdown_weight": 0.20,
      "winrate_weight": 0.15,
      "count_weight": 0.10,
      "consistency_weight": 0.05
    }
  }
}
```

## Strategy Genealogy

Track strategy lineage:

```python
genealogy = {
    "strategy_id": "strat_042",
    "lineage": [
        {"id": "strat_001", "name": "trend_v1", "fitness": 0.62},
        {"id": "strat_015", "name": "trend_v5", "fitness": 0.71},
        {"id": "strat_031", "name": "trend_v8", "fitness": 0.78},
        {"id": "strat_042", "name": "trend_v11", "fitness": 0.83}
    ],
    "mutations": [
        {"op": "param_tweak", "key": "rsi_oversold", "from": 30, "to": 25},
        {"op": "add_rule", "key": "volume_filter", "value": true},
        {"op": "param_tweak", "key": "stop_loss_pct", "from": 0.05, "to": 0.04}
    ]
}
```

## Strategy Registry

All evolved strategies are persisted:

```
~/.claude/strategies/
├── registry.json              # 策略索引
├── archive/                    # 历史策略归档
│   ├── strat_001.json        # v1
│   ├── ...
│   └── strat_042.json         # current best
├── populations/               # 每代种群
│   ├── gen_01.json
│   ├── gen_02.json
│   └── ...
└── genealogies/              # 血缘追踪
    ├── strat_042.json
    └── ...
```

## Scripts

- `scripts/evolution_engine.py` — Main evolution loop
- `scripts/mutation.py` — Mutation operators
- `scripts/backtest_runner.py` — Backtest execution
- `scripts/fitness_scorer.py` — Multi-dimensional fitness scoring
- `scripts/strategy_registry.py` — Persistence and retrieval

## References

- `references/evolution-params.md` — Evolution hyperparameters
- `references/fitness-design.md` — Fitness function design guide
