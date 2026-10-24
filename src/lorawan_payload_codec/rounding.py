"""One rounding rule for every encoder in this repo.

`steps(26.85, 0.1)` must be 269 in Python and in the C encoder, which only has the integer
2685.  Python's `round(26.85 / 0.1)` gives 268 because 26.85 / 0.1 is 268.4999... in binary
floating point and `round` is half-to-even; C's `(2685 + 5) / 10` gives 269.  So the rule is:
work on the exact decimal, and round halves away from zero.  In C that is
`(n + d/2) / d` for n >= 0 and `-((-n + d/2) / d)` for n < 0 (see lib/payload_codec/rounding.h).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def steps(value: float | int, scale: float | int) -> int:
    """`value` in physical units as an exact decimal, divided by `scale`, rounded half away
    from zero (Decimal's ROUND_HALF_UP) to an integer."""
    q = Decimal(str(value)) / Decimal(str(scale))
    return int(q.to_integral_value(rounding=ROUND_HALF_UP))
