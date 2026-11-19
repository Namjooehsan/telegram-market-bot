"""Format-level validation for public cryptocurrency addresses.

This module never accepts or handles private keys, seed phrases, or signing material.
Validation is deliberately conservative and is not a cryptographic checksum check.
"""
import re

PATTERNS = {
    "BTC": re.compile(r"^(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})$"),
    "BCH": re.compile(r"^(?:bitcoincash:)?(?:[qp][a-z0-9]{41}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$", re.I),
    "XRP": re.compile(r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$"),
    "ADA": re.compile(r"^(?:addr1|addr_test1)[a-z0-9]{20,120}$"),
}
EXPLORERS = {
    "BTC": "https://mempool.space/address/{address}",
    "BCH": "https://blockchair.com/bitcoin-cash/address/{address}",
    "XRP": "https://xrpscan.com/account/{address}",
    "ADA": "https://cardanoscan.io/address/{address}",
}


def validate_public_address(network: str, address: str) -> bool:
    network = network.upper().strip()
    address = address.strip()
    pattern = PATTERNS.get(network)
    return bool(pattern and pattern.fullmatch(address))


def explorer_url(network: str, address: str) -> str:
    network = network.upper().strip()
    if network not in EXPLORERS:
        raise ValueError("Unsupported network")
    return EXPLORERS[network].format(address=address)
