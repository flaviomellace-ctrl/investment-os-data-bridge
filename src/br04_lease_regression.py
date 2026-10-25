"""Independent T03 validation for an explicitly incomplete operating lease."""
import math


def valid_partial_operating_lease(row, evidence):
    flags = set(row.get('br04_flags', '').split(';'))
    if 'OPERATING_LEASE_PARTIAL_COMPONENT' not in flags:
        return False
    if flags & {'OPERATING_LEASE_CONFLICTING', 'OPERATING_LEASE_MISSING'}:
        return False
    if row.get('operating_lease_liabilities', '').strip():
        return False
    parts = row.get('operating_lease_liabilities_components', '').split(';')
    if len(parts) != 1 or parts[0].count('=') != 1:
        return False
    tag, raw = parts[0].split('=')
    if tag not in {'OperatingLeaseLiabilityCurrent', 'OperatingLeaseLiabilityNoncurrent'}:
        return False
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(value) or value < 0:
        return False
    selected = [e for e in evidence if e.get('ticker') == row.get('ticker')
                and e.get('adsh') == row.get('annual_adsh')
                and e.get('used_as') in {'operating_lease_candidate_lower_bound', 'operating_lease_liabilities'}]
    if len(selected) != 1:
        return False
    fact = selected[0]
    try:
        observed = float(fact.get('value', ''))
    except (TypeError, ValueError):
        return False
    return (fact.get('used_as') == 'operating_lease_candidate_lower_bound'
            and fact.get('tag') == tag and fact.get('stmt') == 'BS'
            and fact.get('uom') == 'USD' and fact.get('qtrs') == '0'
            and math.isfinite(observed)
            and abs(value-observed) <= 1e-9 * max(1.0, abs(value), abs(observed)))
