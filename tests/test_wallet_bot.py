import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wallet_bot.store import WalletStore
from wallet_bot.validation import validate_public_address, explorer_url


def test_address_format_validation_and_explorer():
    assert validate_public_address("BTC", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
    assert validate_public_address("XRP", "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh")
    assert not validate_public_address("DOGE", "D123")
    assert explorer_url("BTC", "bc1qtest").startswith("https://mempool.space/address/")


def test_store_encrypts_and_scopes_by_user(tmp_path, monkeypatch):
    monkeypatch.setenv("WALLET_DATA_KEY", Fernet.generate_key().decode())
    store = WalletStore(str(tmp_path / "wallet.sqlite3"))
    entry_id = store.add("100", "BTC", "bc1qpublicaddress", "cold storage")
    assert store.list_for_user("100")[0]["id"] == entry_id
    assert store.list_for_user("100")[0]["address"] == "bc1qpublicaddress"
    assert store.list_for_user("200") == []
    assert store.remove("200", entry_id) is False
    assert store.remove("100", entry_id) is True
    assert store.list_for_user("100") == []


def test_store_refuses_plaintext_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("WALLET_DATA_KEY", raising=False)
    with pytest.raises(RuntimeError, match="WALLET_DATA_KEY is required"):
        WalletStore(str(tmp_path / "wallet.sqlite3"))


def test_wrong_key_is_detected_on_reopen(tmp_path, monkeypatch):
    db_path = str(tmp_path / "wallet.sqlite3")
    monkeypatch.setenv("WALLET_DATA_KEY", Fernet.generate_key().decode())
    store = WalletStore(db_path)
    store.add("100", "BTC", "bc1qpublicaddress")

    # A restarted process must fail before polling or accepting new records.
    monkeypatch.setenv("WALLET_DATA_KEY", Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match="does not match"):
        WalletStore(db_path)


def test_store_limits_each_user_to_30_addresses(tmp_path, monkeypatch):
    monkeypatch.setenv("WALLET_DATA_KEY", Fernet.generate_key().decode())
    store = WalletStore(str(tmp_path / "wallet.sqlite3"))
    for i in range(30):
        store.add("100", "BTC", f"bc1qpublicaddress{i}")
    with pytest.raises(ValueError, match="maximum of 30"):
        store.add("100", "BTC", "bc1qpublicaddress31")
    # The limit is per user, not global.
    assert store.add("200", "BTC", "bc1qpublicaddress32") > 0
