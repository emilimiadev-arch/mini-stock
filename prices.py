"""Fetches live USD prices for supported currencies. Results are cached 5 minutes."""

import streamlit as st
import requests

# Currencies supported in the UI
CURRENCIES = ["USD", "USDT", "ARS", "BTC", "ETH", "ADA"]

# CoinGecko IDs for crypto
_COINGECKO = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "ADA": "cardano",
}

_STABLECOINS = {"USD", "USDT"}


@st.cache_data(ttl=300, show_spinner=False)
def get_prices() -> dict[str, float]:
    """
    Returns a dict {currency: usd_price}.
    USD/USDT = 1.0. ARS uses blue dollar rate. BTC/ETH/ADA from CoinGecko.
    Missing prices fall back to 0.0.
    """
    prices: dict[str, float] = {c: 1.0 for c in _STABLECOINS}

    # Crypto prices
    try:
        ids = ",".join(_COINGECKO.values())
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ids, "vs_currencies": "usd"},
            timeout=5,
        )
        data = r.json()
        for currency, coin_id in _COINGECKO.items():
            prices[currency] = float(data.get(coin_id, {}).get("usd", 0.0))
    except Exception:
        for currency in _COINGECKO:
            prices[currency] = 0.0

    # ARS blue dollar (dolarapi.com)
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/blue", timeout=5)
        sell = float(r.json().get("venta") or 0)
        prices["ARS"] = 1.0 / sell if sell else 0.0
    except Exception:
        prices["ARS"] = 0.0

    return prices


def to_usd(amount: float, currency: str, prices: dict[str, float]) -> float:
    return float(amount or 0) * prices.get(currency, 0.0)
