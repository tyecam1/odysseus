"""Simple deterministic SMA-cross baseline strategy (FT-00 smoke).

Not a profitable strategy and not intended to be one: it exists so the
FT-00 dry-run lifecycle has a deterministic, owned, interpretable baseline
to load — the "simple deterministic moving-average trend baseline" the
canonical spec reserves for the first evaluation family (FT-01+).
"""
from pandas import DataFrame
from freqtrade.strategy import IStrategy


class SMACrossBaseline(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    minimal_roi = {"0": 0.15, "720": 0.05}
    stoploss = -0.10
    trailing_stop = False
    startup_candle_count = 60
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_20"] = dataframe["close"].rolling(window=20).mean()
        dataframe["sma_50"] = dataframe["close"].rolling(window=50).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["sma_20"] > dataframe["sma_50"]) & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["sma_20"] < dataframe["sma_50"]) & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        return dataframe
