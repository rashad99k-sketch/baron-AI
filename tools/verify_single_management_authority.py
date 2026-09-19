"""Static production guard: only ExecutionService may invoke close primitives."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {ROOT / "execution" / "execution_service.py"}
CLOSE_NAMES = {"close_position_full", "close_partial"}

violations = []
for path in ROOT.rglob("*.py"):
    if "tests" in path.parts or path in ALLOWED:
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        violations.append((str(path), 0, f"parse:{exc}"))
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in CLOSE_NAMES:
            violations.append((str(path), node.lineno, node.func.id))

if violations:
    for item in violations:
        print("VIOLATION", item)
    raise SystemExit(1)
print("SINGLE_MANAGEMENT_AUTHORITY=PASS")
print("close primitives have exactly one production caller boundary: execution/execution_service.py")
