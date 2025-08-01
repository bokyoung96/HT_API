import pandas as pd
from typing import Any


class Tools:
    @staticmethod
    def convert_data_types(value: Any) -> Any:
        """
        Convert string values to appropriate data types.

        Args:
            value: Value to convert, can be any type

        Returns:
            Converted value in appropriate data type:
            - Returns original value if not a string
            - Converts to float if numeric string (not starting with 0)
            - Converts to datetime if 8-digit date string
            - Returns original string if no conversion possible
        """
        if not isinstance(value, str):
            return value

        value = value.replace(',', '')

        if not value.startswith('0'):
            try:
                return float(value)
            except:
                pass

        try:
            if len(value) == 8 and value.isdigit():
                return pd.to_datetime(value, format='%Y%m%d')
        except:
            pass
        return value
