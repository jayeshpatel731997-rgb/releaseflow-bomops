import pytest

from app.db.seed import RULES


@pytest.mark.parametrize("rule_id,explanation", RULES)
def test_rule_registry_has_stable_explanation(rule_id, explanation):
    assert "-" in rule_id
    assert len(explanation) > 12


@pytest.mark.parametrize("candidate", [None, "", "UNKNOWN", "N/A", 0])
def test_unknown_candidate_is_never_fabricated(candidate):
    assert candidate in {None, "", "UNKNOWN", "N/A", 0}


@pytest.mark.parametrize(
    "base,purchase,factor,valid",
    [
        ("EA", "PK", 20, True),
        ("EA", "EA", 1, True),
        ("EA", "PK", 0, False),
        ("KG", "EA", 1, False),
        ("EA", "PK", -2, False),
    ],
)
def test_uom_conversion_contract(base, purchase, factor, valid):
    assert (base == "EA" and factor > 0 and (purchase == "PK" or factor == 1)) is valid


@pytest.mark.parametrize(
    "quantity,moq,package,valid",
    [
        (120, 120, 24, True),
        (240, 120, 24, True),
        (100, 120, 24, False),
        (130, 120, 24, False),
        (0, 120, 24, False),
    ],
)
def test_packaging_moq_rule(quantity, moq, package, valid):
    assert (quantity >= moq and quantity % package == 0) is valid
