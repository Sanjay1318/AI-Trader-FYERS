"""
Rule Definitions
─────────────────
Individual rule conditions for the rule-based prediction engine.

Each rule is a standalone function that examines a feature vector and
returns a score contribution and a reason string.

Rules are intentionally small, testable, and independent. Later they
can be replaced or augmented by ML model outputs.
"""

from typing import Dict, List, Optional, Tuple


class Rule:
    """A single rule with a name, evaluation function, and weight."""

    def __init__(
        self,
        name: str,
        weight: float,
        description: str,
    ):
        self.name = name
        self.weight = weight
        self.description = description

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        """
        Evaluate this rule against a feature vector.

        Returns:
            (score_contribution, reason_string_or_None)
            score_contribution: positive = bullish, negative = bearish
            reason: human-readable string if rule triggered, else None
        """
        raise NotImplementedError("Subclasses must implement evaluate()")


# ── Trend Rules ──────────────────────────────────────────────────────────────


class EMACrossoverRule(Rule):
    """EMA20 > EMA50 → bullish, EMA20 < EMA50 → bearish."""

    def __init__(self):
        super().__init__(
            name="ema_cross",
            weight=20.0,
            description="EMA20 vs EMA50 crossover",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        ema20 = features.get("ema20")
        ema50 = features.get("ema50")
        if ema20 is None or ema50 is None or ema50 == 0:
            return 0.0, None
        diff = (ema20 - ema50) / ema50
        if diff > 0.002:
            return self.weight, f"EMA20 ({ema20:.1f}) > EMA50 ({ema50:.1f}) — bullish trend"
        elif diff < -0.002:
            return -self.weight, f"EMA20 ({ema20:.1f}) < EMA50 ({ema50:.1f}) — bearish trend"
        return 0.0, None


# ── Momentum Rules ───────────────────────────────────────────────────────────


class RSIRule(Rule):
    """RSI < 40 → oversold/bullish, RSI > 60 → overbought/bearish."""

    def __init__(self):
        super().__init__(
            name="rsi",
            weight=10.0,
            description="RSI overbought/oversold",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        rsi = features.get("rsi")
        if rsi is None:
            return 0.0, None
        if rsi < 35:
            return self.weight, f"RSI {rsi:.1f} — oversold, mean reversion likely"
        elif rsi < 40:
            return self.weight * 0.5, f"RSI {rsi:.1f} — approaching oversold"
        elif rsi > 65:
            return -self.weight, f"RSI {rsi:.1f} — overbought, reversal likely"
        elif rsi > 60:
            return -self.weight * 0.5, f"RSI {rsi:.1f} — approaching overbought"
        return 5.0, f"RSI {rsi:.1f} — neutral range"


class MACDRule(Rule):
    """MACD > Signal → bullish momentum, MACD < Signal → bearish."""

    def __init__(self):
        super().__init__(
            name="macd",
            weight=15.0,
            description="MACD vs Signal crossover",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        macd = features.get("macd")
        signal = features.get("macd_signal")
        if macd is None or signal is None:
            return 0.0, None
        diff = macd - signal
        if diff > 0 and macd > 0:
            return self.weight, f"MACD {macd:.2f} > Signal {signal:.2f} — bullish momentum"
        elif diff > 0:
            return self.weight * 0.5, f"MACD {macd:.2f} > Signal {signal:.2f} — recovering"
        elif diff < 0 and macd < 0:
            return -self.weight, f"MACD {macd:.2f} < Signal {signal:.2f} — bearish momentum"
        elif diff < 0:
            return -self.weight * 0.5, f"MACD {macd:.2f} < Signal {signal:.2f} — weakening"
        return 0.0, None


# ── Volume Rules ─────────────────────────────────────────────────────────────


class VWAPRule(Rule):
    """Price > VWAP → bullish, Price < VWAP → bearish."""

    def __init__(self):
        super().__init__(
            name="vwap",
            weight=15.0,
            description="Price position relative to VWAP",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        close = features.get("close")
        vwap = features.get("vwap")
        if close is None or vwap is None or vwap == 0:
            return 0.0, None
        dist = (close - vwap) / vwap
        if dist > 0.002:
            return self.weight, f"Price {close:.1f} > VWAP {vwap:.1f} — bullish"
        elif dist < -0.002:
            return -self.weight, f"Price {close:.1f} < VWAP {vwap:.1f} — bearish"
        return 0.0, None


class VolumeRule(Rule):
    """Higher relative volume confirms directional move."""

    def __init__(self):
        super().__init__(
            name="volume",
            weight=10.0,
            description="Volume confirmation",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        rel_vol = features.get("relative_volume")
        volume = features.get("volume")
        volume_sma = features.get("volume_sma20")
        if rel_vol is not None and rel_vol > 0:
            if rel_vol > 2.0:
                return self.weight, f"Volume {rel_vol:.1f}x SMA — strong participation"
            elif rel_vol > 1.5:
                return self.weight * 0.5, f"Volume {rel_vol:.1f}x SMA — above average"
        elif volume is not None and volume_sma is not None and volume_sma > 0:
            ratio = volume / volume_sma
            if ratio > 2.0:
                return self.weight, f"Volume {ratio:.1f}x SMA — strong participation"
        return 0.0, None


# ── Regime Rules ─────────────────────────────────────────────────────────────


class RegimeRule(Rule):
    """Regime detection confirms the dominant market direction."""

    REGIME_MAP = {
        "sideways": 0.0,
        "pre_open": 0.0,
        "low_volatility": 0.0,
        "high_volatility": -5.0,
    }

    def __init__(self):
        super().__init__(
            name="regime",
            weight=15.0,
            description="Market regime confirmation",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        regime = features.get("regime", "")
        if isinstance(regime, str):
            regime_lower = regime.lower().strip()
            if "bull" in regime_lower:
                return self.weight, f"Market regime: {regime} — bullish"
            elif "bear" in regime_lower:
                return -self.weight, f"Market regime: {regime} — bearish"
            elif "high_vol" in regime_lower:
                return -5.0, f"Market regime: {regime} — increased risk"
            elif "sideways" in regime_lower or "low_vol" in regime_lower:
                return 5.0, f"Market regime: {regime} — range-bound, mean reversion"
        return 0.0, None


# ── ADX Trend Strength Rule ──────────────────────────────────────────────────


class ADXRule(Rule):
    """ADX measures trend strength. ADX > 25 means strong trend."""

    def __init__(self):
        super().__init__(
            name="adx",
            weight=10.0,
            description="ADX trend strength",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        adx = features.get("adx")
        di_plus = features.get("di_plus")
        di_minus = features.get("di_minus")
        if adx is None or adx <= 0:
            return 0.0, None
        if adx > 25 and di_plus is not None and di_minus is not None:
            if di_plus > di_minus:
                return self.weight, f"ADX {adx:.1f} > 25, +DI > -DI — strong uptrend"
            else:
                return -self.weight, f"ADX {adx:.1f} > 25, -DI > +DI — strong downtrend"
        elif adx > 25:
            return self.weight * 0.5, f"ADX {adx:.1f} — strong trend (direction unclear)"
        elif adx > 20:
            return 3.0, f"ADX {adx:.1f} — trend developing"
        return 0.0, None


# ── Session Rules ────────────────────────────────────────────────────────────


class SessionRule(Rule):
    """Trading session context adds bias."""

    def __init__(self):
        super().__init__(
            name="session",
            weight=5.0,
            description="Session context",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        session = features.get("session", "")
        if isinstance(session, str):
            s = session.lower()
            if s == "open":
                return 5.0, "Session: market open — increased volatility"
            elif s == "close":
                return -3.0, "Session: market close — position squaring"
        return 0.0, None


# ── ATR Volatility Rule ─────────────────────────────────────────────────────


class ATRRule(Rule):
    """ATR measures volatility. High ATR = wider stops needed."""

    def __init__(self):
        super().__init__(
            name="atr",
            weight=5.0,
            description="ATR volatility assessment",
        )

    def evaluate(self, features: Dict[str, float]) -> Tuple[float, Optional[str]]:
        atr = features.get("atr")
        close = features.get("close")
        if atr is None or close is None or close == 0:
            return 0.0, None
        atr_pct = atr / close * 100
        if atr_pct > 0.05:
            return -5.0, f"ATR {atr:.1f} ({atr_pct:.3f}%) — high volatility, use wider stops"
        elif atr_pct < 0.02:
            return 3.0, f"ATR {atr:.1f} ({atr_pct:.3f}%) — low volatility, tighter stops"
        return 0.0, None


# ── All Rules ────────────────────────────────────────────────────────────────


def get_default_rules() -> List[Rule]:
    """Return the standard set of rules for the rule-based predictor."""
    return [
        EMACrossoverRule(),
        RSIRule(),
        MACDRule(),
        VWAPRule(),
        VolumeRule(),
        RegimeRule(),
        ADXRule(),
        SessionRule(),
        ATRRule(),
    ]
