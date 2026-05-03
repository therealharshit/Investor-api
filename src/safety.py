"""Local synchronous safety guard."""

from __future__ import annotations

from src.models import SafetyCategory, SafetyVerdict


BLOCK_MESSAGES: dict[SafetyCategory, str] = {
    SafetyCategory.FRAUD: (
        "I can't help with fraud, forged documents, or hiding losses. "
        "If you want, I can explain legitimate reporting and compliance steps."
    ),
    SafetyCategory.GUARANTEED_RETURNS: (
        "I can't promise guaranteed returns or certainty in market outcomes. "
        "I can help you assess risk, scenarios, and historical context instead."
    ),
    SafetyCategory.INSIDER_TRADING: (
        "I can't help trade on non-public information or confidential tips. "
        "I can explain insider-trading rules and legal investing alternatives."
    ),
    SafetyCategory.MARKET_MANIPULATION: (
        "I can't assist with manipulating markets, wash trading, spoofing, or pump-and-dump behavior. "
        "I can explain how regulators detect and penalize those actions."
    ),
    SafetyCategory.MONEY_LAUNDERING: (
        "I can't help conceal funds, evade reporting, or obscure transaction origins. "
        "I can explain AML rules and compliant brokerage practices."
    ),
    SafetyCategory.RECKLESS_ADVICE: (
        "I can't encourage reckless investing that ignores obvious harm or suitability. "
        "I can help you think through risk, diversification, and safer alternatives."
    ),
    SafetyCategory.SANCTIONS_EVASION: (
        "I can't help bypass sanctions, screening, or tracing controls. "
        "I can explain sanctions compliance and brokerage obligations."
    ),
}


class SafetyGuard:
    """Thin deterministic classifier for obvious harmful intent."""

    def check(self, query: str) -> SafetyVerdict:
        normalized = query.lower()

        # Educational and regulatory questions should pass through.
        educational_markers = (
            "what is",
            "explain",
            "penalty",
            "penalties",
            "legal",
            "illegal",
            "regulation",
            "regulators",
            "detect",
            "investigate",
            "difference between",
            "obligations",
            "requirements",
            "role in preventing",
        )
        if any(marker in normalized for marker in educational_markers):
            return SafetyVerdict(blocked=False)

        block_rules: tuple[tuple[SafetyCategory, tuple[str, ...]], ...] = (
            (
                SafetyCategory.INSIDER_TRADING,
                (
                    "unannounced acquisition",
                    "confidential merger news",
                    "my friend at microsoft gave me a tip",
                    "know the earnings before",
                    "load up before the call",
                    "work at apple and know",
                ),
            ),
            (
                SafetyCategory.MARKET_MANIPULATION,
                (
                    "pump up the price",
                    "coordinated buying scheme",
                    "wash trade",
                    "create volume",
                    "pump and dump",
                    "spoof",
                    "layering",
                ),
            ),
            (
                SafetyCategory.MONEY_LAUNDERING,
                (
                    "without reporting it",
                    "avoid the 10k reporting threshold",
                    "obscure the source of these funds",
                    "hide trading profits from the tax authorities",
                    "structure deposits",
                ),
            ),
            (
                SafetyCategory.GUARANTEED_RETURNS,
                (
                    "guarantee me",
                    "promise me",
                    "100% certain",
                    "foolproof way",
                    "double in a year",
                ),
            ),
            (
                SafetyCategory.RECKLESS_ADVICE,
                (
                    "all my retirement savings in crypto",
                    "take a margin loan to buy more",
                    "entire emergency fund into options",
                    "mortgage my house for",
                ),
            ),
            (
                SafetyCategory.SANCTIONS_EVASION,
                (
                    "bypass ofac sanctions",
                    "sanctioned russian company without it being traced",
                    "route trades through a shell company",
                ),
            ),
            (
                SafetyCategory.FRAUD,
                ("draft a fake contract note",),
            ),
        )

        for category, markers in block_rules:
            if any(marker in normalized for marker in markers):
                return SafetyVerdict(
                    blocked=True,
                    category=category,
                    message=BLOCK_MESSAGES[category],
                )

        return SafetyVerdict(blocked=False)


guard = SafetyGuard()
