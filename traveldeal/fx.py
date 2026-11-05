"""Exchange rates from Frankfurter (https://frankfurter.dev): free, no key, European Central Bank data.

Rates are reference rates published once per working day, so treat conversions as estimates:
your card network's rate on the day the charge posts will differ slightly.
"""

from __future__ import annotations

import json
import urllib.request

CURRENCIES = {
    "USD": "US dollar", "EUR": "Euro", "GBP": "British pound", "CAD": "Canadian dollar", "MXN": "Mexican peso",
    "JPY": "Japanese yen", "AUD": "Australian dollar", "NZD": "New Zealand dollar", "CHF": "Swiss franc",
    "INR": "Indian rupee", "THB": "Thai baht", "SGD": "Singapore dollar", "HKD": "Hong Kong dollar",
    "KRW": "South Korean won", "BRL": "Brazilian real", "ZAR": "South African rand", "SEK": "Swedish krona",
    "NOK": "Norwegian krone", "DKK": "Danish krone", "TRY": "Turkish lira", "ISK": "Icelandic króna",
    "CZK": "Czech koruna", "PLN": "Polish złoty", "HUF": "Hungarian forint", "PHP": "Philippine peso",
    "IDR": "Indonesian rupiah", "MYR": "Malaysian ringgit", "CNY": "Chinese yuan", "ILS": "Israeli shekel",
}
URLS = ("https://api.frankfurter.dev/v1/latest?base={ccy}&symbols=USD",
        "https://api.frankfurter.app/latest?from={ccy}&to=USD")


def usd_rate(ccy: str, timeout: float = 4.0) -> tuple[float, str] | None:
    """US dollars per 1 unit of `ccy`, and the rate's date. None if the service can't be reached."""
    ccy = ccy.upper()
    if ccy == "USD":
        return 1.0, ""
    for url in URLS:
        try:
            req = urllib.request.Request(url.format(ccy=ccy), headers={"User-Agent": "TravelDealSearch/0.5"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            rate = float(data["rates"]["USD"])
            if rate > 0:
                return rate, str(data.get("date", ""))
        except Exception:  # network, HTTP or format problem: try the next URL, then give up
            continue
    return None
