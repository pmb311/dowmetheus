#!/bin/env python3

'''Exporter utility serving Dow 30 share prices to a Prometheus monitoring server.
Comprehensive Prometheus documentation can be found at https://prometheus.io/'''

from abc import ABC, abstractmethod
from collections import defaultdict
from os import getenv
from time import sleep

import argparse
import logging
import unittest

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import requests


# In real life this would be much shorter but sub-15m interval requires a
# more advanced MarketStack subscription tier
COLLECTION_INTERVAL_SECONDS_DEFAULT=900
# Dict of Dow 30 components with their respective exchange keys
SYMBOLS = {
           "AAPL": "XNAS",
           "AMGN": "XNAS",
           "AXP": "XNYS",
           "BA": "XNYS",
           "CAT": "XNYS",
           "CRM": "XNYS",
           "CSCO": "XNAS",
           "CVX": "XNYS",
           "DIS": "XNYS",
           "DOW": "XNYS",
           "GS": "XNYS",
           "HD": "XNYS",
           "HON": "XNYS",
           "IBM": "XNYS",
           "INTC": "XNAS",
           "JNJ": "XNYS",
           "JPM": "XNYS",
           "KO": "XNYS",
           "MCD": "XNYS",
           "MMM": "XNYS",
           "MRK": "XNYS",
           "MSFT": "XNAS",
           "NKE": "XNYS",
           "PG": "XNYS",
           "TRV": "XNYS",
           "UNH": "XNYS",
           "V": "XNYS",
           "VZ": "XNYS",
           "WBA": "XNAS",
           "WMT": "XNYS"
           }
LISTEN_PORT_DEFAULT=9927


class GetMarketStackLastSharePrice(object):
    '''Request an intraday report for a list of symbols from MarketStack at
    specified interval in seconds, using access_key to authenticate.
    Full documentation available at https://marketstack.com/documentation'''
    def __init__(self, symbols: dict, access_key: str, interval: int,
                 url: str = "https://api.marketstack.com/v1/intraday/latest") -> None:
        assert symbols and access_key, "symbols and access key may not be None"
        # Send one request per exchange, and aggregate into a single list
        symbols_by_exchange = defaultdict(list)
        for symbol, exchange in sorted(symbols.items()):
            symbols_by_exchange[exchange].append(symbol)
        self.data = []

        # TODO - parallelize these requests to better synchronize quote timing
        for exchange, symbols_for_exchange in symbols_by_exchange.items():
            logging.debug("About to send GET request to url %s for symbols %s"
                          " on exchange %s",
                          url, symbols_for_exchange, exchange)
            # TODO - paginate replies. There are only 30 Dow components,
            # so we're ok for now
            reply = requests.get(url,
                                 params={"access_key": access_key,
                                         "symbols": ",".join(symbols_for_exchange),
                                         "exchange": exchange,
                                         "interval": f"{interval // 60}min",
                                         "limit": len(symbols.keys())},
                                 timeout=60)
            reply.raise_for_status()
            reply_json = reply.json()
            logging.debug("Received reply %s", reply_json)
            self.data += reply_json["data"]

        self.last_price_map = None

    def get_last_price_map(self) -> dict:
        '''Returns a dict of last price for all symbols'''
        last_price_map = {}
        for record in self.data:
            logging.debug("Parsing record %s", record)
            last_price_map[record["symbol"]] = record["last"]
        self.last_price_map = last_price_map
        return last_price_map

class PrometheusCollector(ABC):
    '''Initialize a process capable of serving key-value pairs in a format
    that can be scraped by a Prometheus monitoring server.
    The metrics are exposed at localhost:<listen_port>/metrics.
    Useful links:
    https://prometheus.io/docs/instrumenting/exporters/
    https://github.com/prometheus/prometheus/wiki/Default-port-allocations'''
    def __init__(self, collection_interval: int = COLLECTION_INTERVAL_SECONDS_DEFAULT,
                 listen_port: int = LISTEN_PORT_DEFAULT) -> None:

        self.collection_interval = collection_interval
        self.listen_port = listen_port

        REGISTRY.register(self)
        start_http_server(self.listen_port)
        while True:
            self.collect()
            sleep(self.collection_interval)

    @abstractmethod
    def collect(self):
        '''Implement the data collection logic here'''

class SharePricePrometheusCollector(PrometheusCollector):
    '''Initialize the exporter object'''
    def __init__(self, symbols: dict, access_key: str, **kwargs) -> None:
        self.symbols = symbols
        self.access_key = access_key
        super(SharePricePrometheusCollector, self).__init__(**kwargs)

    def collect(self) -> GaugeMetricFamily:
        '''Collect share prices for symbols every collection_interval seconds
        and express them as Prometheus metrics'''
        share_prices = GaugeMetricFamily("share_price", "Last share price",
                                         labels=["symbol"])
        obj = GetMarketStackLastSharePrice(self.symbols,
                                           self.access_key,
                                           self.collection_interval)
        last_price_map = obj.get_last_price_map()
        for symbol in self.symbols.keys():
            try:
                last_price = last_price_map[symbol]
                if last_price:
                    share_prices.add_metric([symbol], last_price)
                else:
                    # Report loudly if we encounter a null last price but don't crash
                    logging.error("Last price is None for symbol %s, "
                                  "this is unexpected.", symbol)
            except KeyError:
                # Report loudly if we're missing a symbol but don't crash
                logging.exception("No last price data found for symbol %s, "
                                  "this is unexpected.",
                                  symbol)
        yield share_prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Prometheus exporter for Dow Jones "
                                                 "Industrial Average component "
                                                 "share prices")
    parser.add_argument("--collection-interval", type=int, nargs="?",
                        default=COLLECTION_INTERVAL_SECONDS_DEFAULT,
                        help="Frequency at which to update share prices, in seconds")
    parser.add_argument("--listen-port", type=int, nargs="?",
                        default=LISTEN_PORT_DEFAULT,
                        help="The port that Prometheus will connect to "
                             "and scrape metrics from")
    parser.add_argument("--log-level", type=str, nargs="?", choices=["NOTSET",
                                                                     "DEBUG",
                                                                     "INFO",
                                                                     "WARN",
                                                                     "ERROR",
                                                                     "CRITICAL"],
                        default="ERROR", help="Log level")
    args, unknown = parser.parse_known_args()
    if unknown:
        raise ValueError(f"Unknown arguments encountered - {unknown}. Exiting")

    # Validate that we have an environment variable present for authenticating
    # to the market data source
    api_key = getenv("DATASOURCE_API_KEY")
    assert api_key, "Environment variable DATASOURCE_API_KEY is required to proceed."

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(message)s")
    SharePricePrometheusCollector(SYMBOLS, api_key,
                                  collection_interval=args.collection_interval,
                                  listen_port=args.listen_port)


if __name__ == "__main__":
    main()

class TestDowmetheus(unittest.TestCase):
    '''Unit tests for GetMarketStackLastSharePrice'''

    def test_default_symbol_length(self):
        '''Ensure that there are always 30 Dow symbols'''
        self.assertTrue(len(SYMBOLS) == 30)

    def test_get_last_price_map(self):
        '''Test happy path for GetMarketStackLastSharePrice.get_last_price_map(),
        checking that we have 1 record per symbol'''
        api_key = getenv("DATASOURCE_API_KEY")
        symbols = {"SNAP": "XNYS", "TSLA": "XNAS"}
        obj = GetMarketStackLastSharePrice(symbols, api_key, 900)
        price_map = obj.get_last_price_map()
        self.assertTrue(len(price_map.keys()) == 2)

    def test_null_symbols(self):
        '''Test that passing an empty list of symbols to the
        GetMarketStackLastSharePrice constructor raises an AssertionError'''
        with self.assertRaises(AssertionError):
            GetMarketStackLastSharePrice([], "foo", 900)

    def test_null_apikey(self):
        '''Test that passing an empty access_key to the GetMarketStackLastSharePrice
        constructor raises an AssertionError'''
        with self.assertRaises(AssertionError):
            GetMarketStackLastSharePrice(SYMBOLS, "", 900)
