from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "core" / "engine.py"
PORTFOLIO = ROOT / "portfolio" / "manager.py"
DASHBOARD = ROOT / "dashboard" / "app.py"


def test_legacy_council_is_advisory_only():
    source = ENGINE.read_text(encoding="utf-8")
    block = source[source.index("def council_exit"):source.index("def update_pnl_and_learning")]
    assert "close_position_full(" not in block
    assert "close_partial(" not in block


def test_profit_adapter_has_no_direct_execution_fallback():
    source = ENGINE.read_text(encoding="utf-8")
    block = source[source.index("def _route_management_action"):source.index("def apply_profit_engine")]
    assert "close_position_full(" not in block
    assert "close_partial(" not in block
    assert "manager unavailable" in block


def test_manual_close_routes_to_unified_manager():
    source = ENGINE.read_text(encoding="utf-8")
    block = source[source.index('@app.route("/close"'):source.index('def health()')]
    assert "_execute_action(\"FORCE_EXIT\"" in block
    assert "close_position_full(" not in block


def test_dashboard_manual_close_routes_to_portfolio_authority():
    source = DASHBOARD.read_text(encoding="utf-8")
    block = source[source.index('@app.route("/close"'):source.index('@app.route("/trades"')]
    assert "PORTFOLIO.close_symbol(" in block
    assert "close_position_full(" not in block


def test_portfolio_close_routes_to_live_manager():
    source = PORTFOLIO.read_text(encoding="utf-8")
    start = source.index("def close_symbol")
    next_def = source.find("\n    def ", start + 5)
    block = source[start: next_def if next_def != -1 else len(source)]
    assert "_execute_action(" in block
    assert "self.engine.close_position_full(" not in block
