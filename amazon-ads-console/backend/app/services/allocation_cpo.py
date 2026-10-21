"""Frozen, binding-scoped denominators. Business gaps never erase cost."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext


def ratio(cost, units):
    if cost is None or units is None or units <= 0:
        return None
    with localcontext() as context:
        context.prec = max(80, len(str(cost)) + len(str(units)) + 10)
        return str((Decimal(str(cost)) / Decimal(units)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))


def _date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('BUSINESS_DATE_INVALID')
    return parsed


def _days(start, end):
    while start <= end:
        yield start.isoformat()
        start += timedelta(days=1)


def business_metrics(products, snapshot=None, period=None, report_timezone=None, invalid_reason=None):
    """Local frozen declarations require complete child/day coverage manifests.

    Formal operation still requires independently verified canonical bindings,
    facts and zero-result coverage proofs. Parent fallback is not yet exposed.
    """
    snapshot = snapshot or {}
    bindings, facts = snapshot.get('bindings', []), snapshot.get('facts', [])
    if snapshot and (snapshot.get('period') != period or snapshot.get('report_timezone') != report_timezone or not snapshot.get('id') or not snapshot.get('binding_version')):
        raise ValueError('BUSINESS_SNAPSHOT_SCOPE_MISMATCH')
    if snapshot:
        start = _date(period + '-01')
        end = date(start.year, start.month, monthrange(start.year, start.month)[1])
    index = {}
    for fact in facts:
        key = tuple(fact.get(k) for k in ('account_id', 'marketplace', 'date', 'child_asin'))
        if any(not isinstance(k, str) or not k for k in key) or not fact.get('fact_version') or key in index:
            raise ValueError('BUSINESS_FACT_CONFLICT')
        if not start <= _date(key[2]) <= end:
            raise ValueError('BUSINESS_FACT_OUTSIDE_PERIOD')
        units = fact.get('ordered_product_units')
        if type(units) is not int or units < 0:
            raise ValueError('BUSINESS_UNITS_INVALID')
        index[key] = fact
    used, output = set(), []
    for product in products:
        product_id = product.get('id') or product.get('product_id')
        selected = [b for b in bindings if b.get('product_id') == product_id]
        status, units, denominator_unit = invalid_reason or 'BINDING_MISSING', None, None
        if selected:
            status, units = 'MATCHED', 0
            local_keys = set()
            for binding in selected:
                if binding.get('confirmed') is not True or not binding.get('evidence_id') or not binding.get('effective_from') or not binding.get('effective_to'):
                    status = 'BINDING_UNVERIFIED'
                    break
                bstart, bend = _date(binding['effective_from']), _date(binding['effective_to'])
                if bstart > bend:
                    raise ValueError('BUSINESS_BINDING_PERIOD_INVALID')
                bstart, bend = max(start, bstart), min(end, bend)
                if bstart > bend:
                    status = 'BINDING_OUTSIDE_PERIOD'
                    break
                bunit = binding.get('unit')
                if not binding.get('unit_evidence_id') or bunit not in {'双', '件'} or product.get('unit') != bunit or denominator_unit not in (None, bunit):
                    status = 'BUSINESS_UNIT_UNVERIFIED'
                    break
                denominator_unit = bunit
                children = binding.get('child_asins', [])
                if not children or len(set(children)) != len(children):
                    status = 'BINDING_UNVERIFIED'
                    break
                for child in children:
                    coverage = [c for c in snapshot.get('coverage', []) if (c.get('account_id'), c.get('marketplace'), c.get('child_asin')) == (binding.get('account_id'), binding.get('marketplace'), child)]
                    expected = set(_days(bstart, bend))
                    covered, empty = set(), set()
                    for manifest in coverage:
                        if manifest.get('complete') is not True or not manifest.get('evidence_id'):
                            continue
                        cstart, cend = _date(manifest['date_from']), _date(manifest['date_to'])
                        if cstart > cend:
                            raise ValueError('BUSINESS_COVERAGE_PERIOD_INVALID')
                        zero_dates = manifest.get('empty_dates', [])
                        if not isinstance(zero_dates, list) or len(set(zero_dates)) != len(zero_dates) or any(not cstart <= _date(day) <= cend for day in zero_dates):
                            raise ValueError('BUSINESS_EMPTY_PROOF_OUTSIDE_COVERAGE')
                        covered.update(_days(max(bstart, cstart), min(bend, cend)))
                        empty.update(zero_dates)
                    if not expected.issubset(covered):
                        status = 'BUSINESS_COVERAGE_INCOMPLETE'
                        break
                    for day in sorted(expected):
                        key = (binding.get('account_id'), binding.get('marketplace'), day, child)
                        if key in local_keys or key in used:
                            raise ValueError('BUSINESS_DENOMINATOR_REUSED')
                        local_keys.add(key)
                        fact = index.get(key)
                        if fact:
                            if day in empty:
                                raise ValueError('BUSINESS_EMPTY_PROOF_CONFLICT')
                            units += fact['ordered_product_units']
                        elif day not in empty:
                            status = 'BUSINESS_FACT_MISSING'
                            break
                    if status != 'MATCHED':
                        break
                if status != 'MATCHED':
                    break
            if status == 'MATCHED':
                used.update(local_keys)
                if units == 0:
                    status = 'ZERO_UNITS'
            else:
                units = None
        final = product.get('final_cost')
        ad_units = product.get('attributed_units', product.get('ad_units', product.get('units')))
        output.append(dict(product, ordered_product_units=units, denominator_status=status,
                           denominator_unit=denominator_unit if units is not None else None,
                           allocation_business_cpo=ratio(final, units),
                           allocation_attributed_unit_cost=ratio(final, ad_units),
                           daily_business_cpo=None, business_snapshot_id=snapshot.get('id'),
                           business_binding_version=snapshot.get('binding_version')))
    return output
