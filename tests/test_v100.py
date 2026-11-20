"""Engine 1.0.0, the frozen rule-based baseline.

C1 fix (runs/formal_model_check.md): each morning a counterfeit posts round(brands.counterfeit_price_factor x the
posted price of the stall bearing the original's name). A white-label licensee is the only stall bearing its fresh
name, so a counterfeit of it follows its price; an owner-branded licensee shares the owner's name, and the owner's
price is the one followed. Every reference cell of 0.20.0 (and through it every earlier engine) reproducing at
1.0.0 is checked by tests/test_v0210.py::test_defaults_reproduce_0200."""
from types import SimpleNamespace

from engine import ENGINE_VERSION
from engine.brands import BrandBook, counterfeit_price, morning_prices, premium_price
from engine.config import load


def _cfg(phi=0.8):
    return load(overrides=["brands.enabled=true", "brands.premium=0.4", f"brands.counterfeit_price_factor={phi}",
                           "licensing.brand=white_label", "pricing.deceptive_price_factor=0.7"], mode="bazaar")


def _st(sid, brand, stype, rating=None, licensed_from=None, white_label=False, counterfeit_of=None):
    return SimpleNamespace(sid=sid, brand=brand, category="fish", stype=stype, rating=rating, price_cents=0,
                           licensed_from=licensed_from, white_label=white_label, counterfeit_of=counterfeit_of)


def _book(stalls, ratings):
    book = BrandBook(stalls)
    book.ratings.update(ratings)
    return book


def test_version():
    assert ENGINE_VERSION == "1.0.0"


def test_counterfeit_of_white_label_follows_its_price():
    cfg = _cfg()
    owner = _st("s0", "Alder", "genuine")
    wl = _st("s1", "Birch", "deceptive", licensed_from="s0", white_label=True)
    cf = _st("s2", "Birchh", "deceptive", counterfeit_of="Birch")
    stalls = [owner, wl, cf]
    morning_prices(cfg, stalls, _book(stalls, {"Alder": 0.9, "Birch": 0.8, "Birchh": 0.3}))
    assert wl.price_cents == premium_price(cfg, wl, 0.8)
    assert cf.price_cents == counterfeit_price(cfg, wl.price_cents)
    assert cf.price_cents != premium_price(cfg, cf, 0.3)     # 0.21.0 posted this, its own rule's price


def test_counterfeit_of_owner_brand_follows_the_owner_not_a_licensee():
    cfg = _cfg()
    owner = _st("s0", "Alder", "genuine")
    lic = _st("s1", "Alder", "deceptive", licensed_from="s0")      # owner-branded: shares the name
    cf = _st("s2", "Aldr", "deceptive", counterfeit_of="Alder")
    stalls = [owner, cf, lic]                                       # licensee last: a dict would keep it if let in
    morning_prices(cfg, stalls, _book(stalls, {"Alder": 0.9, "Aldr": None}))
    assert owner.price_cents != lic.price_cents                     # tiers differ (licensing re-prices it later)
    assert cf.price_cents == counterfeit_price(cfg, owner.price_cents)


def test_counterfeit_without_holder_keeps_its_own_price():
    cfg = _cfg()
    cf = _st("s2", "Gone", "deceptive", counterfeit_of="Elm")
    stalls = [_st("s0", "Alder", "genuine"), cf]
    morning_prices(cfg, stalls, _book(stalls, {"Alder": 0.9, "Gone": 0.4}))
    assert cf.price_cents == premium_price(cfg, cf, 0.4)

