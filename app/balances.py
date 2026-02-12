"""Balance computation and debt simplification — ported from frontend."""

# Currency decimal places (must match frontend lib/currency.ts)
CURRENCY_DECIMALS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "CAD": 2,
    "AUD": 2,
    "CHF": 2,
    "HKD": 2,
    "SGD": 2,
    "THB": 2,
    "KRW": 0,
    "INR": 2,
    "CNY": 2,
    "NZD": 2,
    "MXN": 2,
}


def calculate_split(
    total: int,
    method: str,
    involved_members: list[str],
    split_details: dict[str, float],
) -> dict[str, int]:
    """Calculate how an expense is split among members.

    Mirrors frontend splits.ts calculateSplit().
    """
    result: dict[str, int] = {}

    if method == "even":
        count = len(involved_members)
        if count == 0:
            return result
        base = total // count
        remainder = total - base * count
        for i, mid in enumerate(involved_members):
            result[mid] = base + (1 if i < remainder else 0)

    elif method == "percentage":
        allocated = 0
        for i, mid in enumerate(involved_members):
            if i == len(involved_members) - 1:
                result[mid] = total - allocated
            else:
                share = int(total * (split_details.get(mid, 0)) / 100 + 0.5)
                result[mid] = share
                allocated += share

    elif method == "amount":
        for mid in involved_members:
            result[mid] = int(split_details.get(mid, 0))

    elif method == "ratio":
        total_weight = sum(split_details.get(mid, 0) for mid in involved_members)
        if total_weight == 0:
            for mid in involved_members:
                result[mid] = 0
        else:
            allocated = 0
            for i, mid in enumerate(involved_members):
                if i == len(involved_members) - 1:
                    result[mid] = total - allocated
                else:
                    share = int(total * (split_details.get(mid, 0)) / total_weight + 0.5)
                    result[mid] = share
                    allocated += share

    return result


def compute_net_balances(
    expenses: list[dict],
    settlements: list[dict],
    trip_currency: str,
) -> dict[str, dict[str, int]]:
    """Compute per-currency, per-member net balances.

    Returns {currency: {memberId: balance}}.
    """
    balances: dict[str, dict[str, int]] = {}

    def ensure(currency: str, member_id: str) -> None:
        if currency not in balances:
            balances[currency] = {}
        if member_id not in balances[currency]:
            balances[currency][member_id] = 0

    for expense in expenses:
        currency = expense.get("currency") or trip_currency
        splits = calculate_split(
            expense["amount"],
            expense["splitMethod"],
            expense["involvedMembers"],
            expense["splitDetails"],
        )

        ensure(currency, expense["paidBy"])
        balances[currency][expense["paidBy"]] += expense["amount"]

        for member_id, share in splits.items():
            ensure(currency, member_id)
            balances[currency][member_id] -= share

    for settlement in settlements:
        currency = settlement.get("currency") or trip_currency
        ensure(currency, settlement["from"])
        ensure(currency, settlement["to"])
        balances[currency][settlement["from"]] += settlement["amount"]
        balances[currency][settlement["to"]] -= settlement["amount"]

    return balances


def get_settled_by_map(members: list[dict]) -> dict[str, str]:
    """Build member -> payer map from settled_by_id fields."""
    result: dict[str, str] = {}
    for m in members:
        if m.get("settled_by_id"):
            result[m["id"]] = m["settled_by_id"]
    return result


def merge_balances(
    member_balances: dict[str, int],
    settled_by: dict[str, str],
) -> dict[str, int]:
    """Fold grouped members' balances into their payer's balance."""
    merged = dict(member_balances)
    for member_id, payer_id in settled_by.items():
        if member_id not in merged:
            continue
        if payer_id not in merged:
            merged[payer_id] = 0
        merged[payer_id] += merged[member_id]
        del merged[member_id]
    return merged


def convert_amount(
    amount: int,
    from_currency: str,
    to_currency: str,
    rate: float,
) -> int:
    """Convert an integer amount between currencies using a rate.

    Uses int(x + 0.5) to match JavaScript Math.round() (round half up).
    """
    from_decimals = CURRENCY_DECIMALS.get(from_currency, 2)
    to_decimals = CURRENCY_DECIMALS.get(to_currency, 2)
    display_amount = amount / (10 ** from_decimals)
    return int(display_amount * rate * (10 ** to_decimals) + 0.5)


def get_conversion_rate(
    from_currency: str,
    to_currency: str,
    rates: dict,
) -> float | None:
    """Derive conversion rate between two currencies.

    rates has {"target": str, "rates": {currency: rate_to_target}}.
    """
    if from_currency == to_currency:
        return 1.0

    target = rates["target"]
    from_to_target = 1.0 if from_currency == target else rates["rates"].get(from_currency)
    to_to_target = 1.0 if to_currency == target else rates["rates"].get(to_currency)

    if from_to_target is None or to_to_target is None:
        return None

    return from_to_target / to_to_target


def convert_balances_to_currency(
    net_balances: dict[str, dict[str, int]],
    target_currency: str,
    rates: dict,
) -> dict[str, int]:
    """Collapse multi-currency balances into a single target currency."""
    combined: dict[str, int] = {}

    for currency, member_balances in net_balances.items():
        for member_id, balance in member_balances.items():
            if member_id not in combined:
                combined[member_id] = 0

            if currency == target_currency:
                combined[member_id] += balance
            else:
                rate = rates["rates"].get(currency)
                if rate is None:
                    continue
                combined[member_id] += convert_amount(balance, currency, target_currency, rate)

    return combined


def _greedy_simplify(
    effective: dict[str, int],
    currency: str,
) -> list[dict]:
    """Run the greedy debt simplification algorithm for a single currency."""
    creditors = []
    debtors = []

    for member_id, balance in effective.items():
        if balance > 0:
            creditors.append({"id": member_id, "amount": balance})
        elif balance < 0:
            debtors.append({"id": member_id, "amount": -balance})

    creditors.sort(key=lambda x: x["amount"], reverse=True)
    debtors.sort(key=lambda x: x["amount"], reverse=True)

    debts = []
    ci = 0
    di = 0

    while ci < len(creditors) and di < len(debtors):
        transfer = min(creditors[ci]["amount"], debtors[di]["amount"])
        if transfer > 0:
            debts.append({
                "from": debtors[di]["id"],
                "to": creditors[ci]["id"],
                "amount": transfer,
                "currency": currency,
            })
        creditors[ci]["amount"] -= transfer
        debtors[di]["amount"] -= transfer
        if creditors[ci]["amount"] == 0:
            ci += 1
        if debtors[di]["amount"] == 0:
            di += 1

    return debts


def apply_member_settlement_currencies(
    debts: list[dict],
    members: list[dict],
    rates: dict,
) -> list[dict]:
    """Convert debts to creditor's preferred settlement currency."""
    member_currency_map: dict[str, str] = {}
    for m in members:
        if m.get("settlementCurrency"):
            member_currency_map[m["id"]] = m["settlementCurrency"]

    if not member_currency_map:
        return debts

    result = []
    for debt in debts:
        preferred = member_currency_map.get(debt["to"])
        if not preferred or preferred == debt["currency"]:
            result.append(debt)
            continue

        rate = get_conversion_rate(debt["currency"], preferred, rates)
        if rate is None:
            result.append(debt)
            continue

        result.append({
            **debt,
            "amount": convert_amount(debt["amount"], debt["currency"], preferred, rate),
            "currency": preferred,
        })
    return result


def consolidate_opposite_debts(
    debts: list[dict],
    members: list[dict],
    rates: dict,
) -> list[dict]:
    """Net opposite flows between the same pair of members."""

    def pair_key(a: str, b: str) -> str:
        return f"{a}|{b}" if a < b else f"{b}|{a}"

    pairs: dict[str, list[dict]] = {}
    for debt in debts:
        key = pair_key(debt["from"], debt["to"])
        if key not in pairs:
            pairs[key] = []
        pairs[key].append(debt)

    member_currency_map: dict[str, str] = {}
    for m in members:
        if m.get("settlementCurrency"):
            member_currency_map[m["id"]] = m["settlementCurrency"]

    result: list[dict] = []

    for pair_debts in pairs.values():
        has_opposite = any(
            any(other["from"] == d["to"] and other["to"] == d["from"] for other in pair_debts)
            for d in pair_debts
        )

        if not has_opposite:
            result.extend(pair_debts)
            continue

        member_a = pair_debts[0]["from"]
        member_b = pair_debts[0]["to"]
        target_currency = rates["target"]

        net_in_target = 0
        bail = False
        for debt in pair_debts:
            rate = get_conversion_rate(debt["currency"], target_currency, rates)
            if rate is None:
                result.extend(pair_debts)
                bail = True
                break
            amount_in_target = convert_amount(debt["amount"], debt["currency"], target_currency, rate)
            if debt["from"] == member_a and debt["to"] == member_b:
                net_in_target += amount_in_target
            else:
                net_in_target -= amount_in_target

        if bail:
            continue
        if net_in_target == 0:
            continue

        net_from = member_a if net_in_target > 0 else member_b
        net_to = member_b if net_in_target > 0 else member_a
        abs_amount = abs(net_in_target)

        creditor_preferred = member_currency_map.get(net_to)
        final_currency = creditor_preferred or target_currency

        if final_currency == target_currency:
            result.append({"from": net_from, "to": net_to, "amount": abs_amount, "currency": target_currency})
        else:
            rate = get_conversion_rate(target_currency, final_currency, rates)
            if rate is None:
                result.append({"from": net_from, "to": net_to, "amount": abs_amount, "currency": target_currency})
            else:
                result.append({
                    "from": net_from,
                    "to": net_to,
                    "amount": convert_amount(abs_amount, target_currency, final_currency, rate),
                    "currency": final_currency,
                })

    return result


def simplify_debts(
    net_balances: dict[str, dict[str, int]],
    settled_by: dict[str, str],
    members: list[dict],
    rates: dict | None = None,
) -> list[dict]:
    """Simplify debts per-currency with greedy algorithm.

    Returns list of {from, to, amount, currency} dicts.
    """
    debts: list[dict] = []

    for currency, member_balances in net_balances.items():
        effective = merge_balances(member_balances, settled_by)
        debts.extend(_greedy_simplify(effective, currency))

    if rates:
        converted = apply_member_settlement_currencies(debts, members, rates)
        return consolidate_opposite_debts(converted, members, rates)

    return debts


def simplify_debts_in_currency(
    net_balances: dict[str, dict[str, int]],
    settled_by: dict[str, str],
    target_currency: str,
    rates: dict,
    members: list[dict],
) -> list[dict]:
    """Simplify debts consolidated into a single settlement currency."""
    combined = convert_balances_to_currency(net_balances, target_currency, rates)
    effective = merge_balances(combined, settled_by)
    debts = _greedy_simplify(effective, target_currency)
    converted = apply_member_settlement_currencies(debts, members, rates)
    return consolidate_opposite_debts(converted, members, rates)
