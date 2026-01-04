from typing import Tuple

from pydantic_settings import BaseSettings


class GeneralSettings(BaseSettings):
    energy_qty_to_alert: int = 3
    energy_qty_to_consume_apple: int = 5
    energy_qty_restored_by_apple: int = 3
    rounds_left_to_alert: int = 3

    next_step_wait: Tuple = ('wait', '', None)


general_settings = GeneralSettings()
