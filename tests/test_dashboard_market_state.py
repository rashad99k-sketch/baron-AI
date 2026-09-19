from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")


def test_dashboard_contract_exposes_backend_market_state():
    assert '"market_state":' in DASH
    for field in (
        "ema", "vwap", "accumulation", "distribution", "microstructure",
        "data_quality", "transition_state", "reasons",
    ):
        assert field in DASH


def test_dashboard_has_institutional_market_state_panel():
    for token in (
        "MARKET STATE",
        "EMA50 / EMA200",
        "VWAP VALUE",
        "ACCUMULATION",
        "DISTRIBUTION",
        "MICROSTRUCTURE",
    ):
        assert token in DASH
