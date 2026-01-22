from django import template
import decimal

register = template.Library()

@register.filter(name='indian_currency')
def indian_currency(value):
    """
    Formats a number into Indian currency format (e.g., 1,23,456.78).
    """
    if value is None or value == '':
        return "0.00"
    try:
        # Ensure it's a decimal and round to 2 places
        val = decimal.Decimal(str(value)).quantize(decimal.Decimal("0.01"))
        str_val = f"{val:.2f}"
        parts = str_val.split('.')
        integer_part = parts[0]
        decimal_part = parts[1]

        # Indian formatting logic (Lakhs/Crores)
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        
        if remaining:
            # Reverse remaining, chunk by 2, join with comma, reverse back
            formatted_remaining = ",".join([remaining[max(i-2,0):i] for i in range(len(remaining), 0, -2)][::-1])
            formatted_integer = f"{formatted_remaining},{last_three}"
        else:
            # Number is less than 1000
            formatted_integer = integer_part

        return f"{formatted_integer}.{decimal_part}"

    except (ValueError, TypeError, decimal.InvalidOperation):
        return value # Return original if formatting fails