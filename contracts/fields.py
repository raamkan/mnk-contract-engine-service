from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from rest_framework import serializers


class HalfUpDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, float):
            raise serializers.ValidationError("Send amounts as decimal strings, not floats.")
        return super().to_internal_value(data)

    def validate_precision(self, value):
        # Round before DRF checks decimal places, so "0.005" becomes "0.01".
        try:
            with localcontext() as context:
                context.prec = self.max_digits + 2
                value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            self.fail("max_digits", max_digits=self.max_digits)
        return super().validate_precision(value)
