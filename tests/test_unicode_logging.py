from utils.logger import sanitize_for_output


def test_sanitize_for_output_keeps_ascii_safe_text():
    text = "Signal: vwap_momentum_breakout → CALL"
    sanitized = sanitize_for_output(text)
    assert "→" not in sanitized
    assert "CALL" in sanitized
