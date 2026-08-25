# Ponytail supervision policy

Ponytail is the repository's minimalism supervisor. It is not allowed to override the 42 subject, evaluator behavior, exact source-location correctness, or the active issue acceptance criteria.

## Runtime policy

- Coding/refactor/review default: `full`.
- After each non-trivial slice: `/ponytail-review`.
- At milestone/release/defense boundaries: `/ponytail-audit`.
- `ultra`: only when Mario explicitly requests an aggressive simplification pass.
- `off`: temporary plugin-conflict diagnosis only, with the reason recorded.

## Mandatory preservation rules
Never simplify away:

- exact source `file_path` values;
- original character span fidelity;
- max source span enforcement;
- required Python Fire CLI commands/options;
- required Pydantic output models;
- graceful evaluator edge cases;
- persisted index needed for throughput;
- required lexical retrieval method;
- Qwen compatibility;
- meaningful recall/performance tests and evidence.

## Typical YAGNI targets
Before adding anything, ask whether the current issue can be solved by reuse, stdlib, an already-installed dependency, or less code. Be especially skeptical of semantic indexes before mandatory pass, DI containers, repositories/interfaces with one implementation, databases, workers, async infrastructure, web APIs, caches, elaborate config frameworks, and abstraction-only modules.
