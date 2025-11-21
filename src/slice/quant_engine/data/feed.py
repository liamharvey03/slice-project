# src/slice/quant_engine/data/feed.py

import backtrader as bt

class SlicePandasData(bt.feeds.PandasData):
    """
    Backtrader datafeed with explicit column mappings.
    """
    params = (
        ('datetime', None),
        ('open',     'open'),
        ('high',     'high'),
        ('low',      'low'),
        ('close',    'close'),
        ('volume',   'volume'),
        ('openinterest', None),
    )