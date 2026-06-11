from grimoire_mcp.rules import (
    EXTRACTION_INSTRUCTIONS,
    RULE_CATEGORIES,
    is_test_path,
    rule_id,
    rule_signal_score,
)


def test_signal_score_positive_for_rule_bearing_code():
    code = "def discount(total):\n    if total > 100:\n        return total * 0.1\n    return 0\n"
    assert rule_signal_score(code) > 0


def test_signal_score_zero_for_plain_code():
    code = "def greet(name):\n    return f'hello {name}'\n"
    assert rule_signal_score(code) == 0


def test_signal_score_is_density():
    dense = "if a > 1: raise X\nif b < 2: raise Y\n"
    sparse = "if a > 1:\n    pass\n" + ("x = 1\n" * 20)
    assert rule_signal_score(dense) > rule_signal_score(sparse)


def test_is_test_path():
    assert is_test_path("tests/test_users.py")
    assert is_test_path("src/__tests__/orders.spec.ts")
    assert is_test_path("src/orders.test.ts")
    assert not is_test_path("src/contest_winner.py")  # "test" no meio de palavra não conta
    assert not is_test_path("src/orders.ts")


def test_rule_id_deterministic_and_distinct():
    a = rule_id("src/users.py", "CPF deve ter 11 dígitos")
    assert a == rule_id("src/users.py", "CPF deve ter 11 dígitos")
    assert a != rule_id("src/orders.ts", "CPF deve ter 11 dígitos")
    assert len(a) == 12


def test_instructions_mention_contract():
    for needle in ("save_rules", "confidence", "category", *sorted(RULE_CATEGORIES)):
        assert needle in EXTRACTION_INSTRUCTIONS
