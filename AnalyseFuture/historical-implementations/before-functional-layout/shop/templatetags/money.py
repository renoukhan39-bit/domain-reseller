"""Money is stored in integer paise and displayed with two decimal places."""
from decimal import Decimal
from django import template
register = template.Library()

@register.filter

def inr(paise):
    try:
        return f"{(Decimal(int(paise)) / 100):,.2f}"
    except (ValueError, TypeError, ArithmeticError):
        return "—"
