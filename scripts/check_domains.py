#!/usr/bin/env python3
"""Rank candidate domain names by availability, TLD fit, and first-year price.

Queries rdap.org (stdlib only, no deps). Tweak NAMES/TLDs/weights as needed.
Prices are manually researched (April 2026, cheapest registrar first-year promo).
"""

from __future__ import annotations

import itertools
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

TLD_PRICES_USD: dict[str, float] = {
    "com":     2.90,
    "io":     14.98,
    "ai":     65.00,
    "dev":    10.00,
    "app":    10.00,
    "co":      9.00,
    "net":    11.20,
    "xyz":     0.98,
    "tech":    4.00,
    "cloud":   4.00,
    "trade":   2.99,
    "fund":    5.98,
    "capital": 5.99,
    "finance": 8.98,
}

TLD_PRESTIGE: dict[str, float] = {
    "com": 1.00, "io": 0.90, "ai": 0.85, "dev": 0.75, "app": 0.70,
    "co":  0.70, "net": 0.60, "trade": 0.55, "fund": 0.55, "capital": 0.55,
    "finance": 0.55, "cloud": 0.50, "tech": 0.45, "xyz": 0.25,
}

NAMES: list[str] = [
    "quantplatform", "quantforge", "quantlab", "quantstack",
    "quantdeck", "quantflow", "quantwave", "quantkit",
    "quantbase", "quantstudio", "quanthub", "quantcore",
    "quantnest", "quantspace", "quantpilot", "quantloop",
    "pyquant", "openquant", "purequant", "altquant",
    "goquant", "trustquant", "zeroquant", "metaquant",
]


@dataclass(frozen=True)
class Result:
    name: str
    tld: str
    available: bool | None  # None = unknown (query error / TLD unsupported)
    price_usd: float
    score: float


def check_rdap(domain: str, timeout: float = 10.0, max_attempts: int = 4) -> bool | None:
    """True = available, False = registered, None = unknown.

    urllib follows the 302 from rdap.org to the authoritative registry RDAP.
    2xx means the domain exists; 404 means not found (available).
    Retries with exponential backoff on 429 (rate limited) and transient errors.
    """
    url = f"https://rdap.org/domain/{domain}"
    req = urllib.request.Request(
        url, headers={"Accept": "application/rdap+json", "User-Agent": "check-domains/1.0"}
    )
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return False if 200 <= resp.status < 300 else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return True
            if e.code == 429 and attempt < max_attempts - 1:
                time.sleep(2 ** attempt + 0.5 * attempt)
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < max_attempts - 1:
                time.sleep(1 + attempt)
                continue
            return None
    return None


def score(name: str, tld: str, price: float) -> float:
    # Shorter names are punchier; 6 chars ~ ideal, 16+ ~ poor.
    length_score = max(0.0, 1.0 - max(0, len(name) - 6) / 10)
    prestige = TLD_PRESTIGE.get(tld, 0.3)
    # Price scaled so $0=1.0, $70=0.0 (since .ai sits at the top).
    price_score = max(0.0, 1.0 - price / 70)
    return 0.40 * prestige + 0.35 * length_score + 0.25 * price_score


def main() -> int:
    combos = list(itertools.product(NAMES, TLD_PRICES_USD.keys()))
    print(f"Checking {len(combos)} domains via rdap.org...", file=sys.stderr)

    # Serial with pacing — rdap.org rate-limits aggressively. Concurrency would
    # just multiply the 429s and force backoff retries, ending up slower overall.
    results: list[Result] = []
    inter_request_delay = 0.4
    for i, (name, tld) in enumerate(combos, 1):
        available = check_rdap(f"{name}.{tld}")
        price = TLD_PRICES_USD[tld]
        results.append(Result(
            name=name, tld=tld, available=available, price_usd=price,
            score=score(name, tld, price) if available else 0.0,
        ))
        if i % 25 == 0:
            print(f"  {i}/{len(combos)}", file=sys.stderr)
        time.sleep(inter_request_delay)

    available_results = [r for r in results if r.available is True]
    available_results.sort(key=lambda r: r.score, reverse=True)

    unknown_count = sum(1 for r in results if r.available is None)
    taken_count = sum(1 for r in results if r.available is False)

    print(f"\nStats: {len(available_results)} available, {taken_count} taken, "
          f"{unknown_count} unknown (RDAP errors / unsupported TLDs)")

    header = f"{'score':>5}  {'domain':<28} {'1st-yr USD':>10}  {'~CAD':>6}"

    print("\n=== Top 10 overall ===")
    print(header)
    print("-" * 60)
    for r in available_results[:10]:
        cad = r.price_usd * 1.37
        print(f"{r.score:>5.3f}  {r.name + '.' + r.tld:<28} "
              f"${r.price_usd:>8.2f}  C${cad:>4.0f}")

    print("\n=== Top 3 per TLD ===")
    by_tld: dict[str, list[Result]] = {}
    for r in available_results:
        by_tld.setdefault(r.tld, []).append(r)
    for tld in TLD_PRICES_USD:
        rows = by_tld.get(tld, [])
        if not rows:
            continue
        print(f"\n.{tld} (${TLD_PRICES_USD[tld]:.2f} USD / ~C${TLD_PRICES_USD[tld]*1.37:.0f}):")
        for r in rows[:3]:
            print(f"  {r.score:>5.3f}  {r.name}.{r.tld}")

    if unknown_count:
        print(f"\nNote: {unknown_count} lookups returned unknown — re-run or "
              f"verify manually for these TLDs if interested.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
