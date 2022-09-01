from abc import ABC, abstractmethod
from os import getenv
from time import sleep

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import argparse
import logging
import requests

# In real life this would be much shorter but sub-15m interval requires a more advanced
# MarketStack subscription tier
COLLECTION_INTERVAL_SECONDS_DEFAULT=900
# Dow 30
SYMBOLS = [
           "AAPL",
           "AMGN",
           "AXP",
           "BA",
           "CAT",
           "CRM",
           "CSCO",
           "CVX",
           "DIS",
           "DOW",
           "GS",
           "HD",
           "HON",
           "IBM",
           "INTC",
           "JNJ",
           "JPM",
           "KO",
           "MCD",
           "MMM",
           "MRK",
           "MSFT",
           "NKE",
           "PG",
           "TRV",
           "UNH",
           "V",
           "VZ",
           "WBA",
           "WMT",
          ]
LISTEN_PORT_DEFAULT=9927


class GetMarketStackLastSharePrice(object):
    def __init__(self, symbols, access_key, url="https://api.marketstack.com/v1/intraday/latest"):
        '''Request an intraday report for a list of symbols from MarketStack,
        using access_key to authenticate. Full documentation available at
        https://marketstack.com/documentation'''
        
        assert symbols and access_key, "symbols and access key may not resolve to None"
        logging.debug("About to send GET request to url {} for symbols {}".format(url, symbols))
        # TODO - paginate replies. For this use case the largest observed record set
        # is less than 300, so we're ok for now
        reply = requests.get(url, params={"access_key": access_key,
                                          "symbols": ",".join(symbols),
                                          "limit": 1000})
        reply.raise_for_status()
        reply_json = reply.json()
        logging.debug("Received reply {}".format(reply_json))
        self.data = reply_json["data"]
        self.last_price_map = None
    
    def get_last_price_map(self):
        '''Returns a dict of last price for all symbols'''
        last_price_map = {}
        for record in self.data:
            logging.debug("Parsing record {}".format(record))
            last_price_map[record["symbol"]] = record["last"]
        self.last_price_map = last_price_map
        return last_price_map

class PrometheusCollector(ABC):
    def __init__(self, collection_interval=COLLECTION_INTERVAL_SECONDS_DEFAULT,
                 listen_port=LISTEN_PORT_DEFAULT):
        '''Initialize a process capable of serving key-value pairs in a format that can be scraped
        by a Prometheus monitoring server. Useful links:
        https://prometheus.io/
        https://github.com/prometheus/prometheus/wiki/Default-port-allocations'''

        self.collection_interval = collection_interval
        self.listen_port = listen_port

        REGISTRY.register(self)
        start_http_server(self.listen_port)
        while True:
            self.collect()
            sleep(self.collection_interval)
    
    @abstractmethod
    def collect(self):
        pass

class SharePricePrometheusCollector(PrometheusCollector):
    def __init__(self, symbols, access_key, **kwargs):
        self.symbols = symbols
        self.access_key = access_key
        super(SharePricePrometheusCollector, self).__init__(**kwargs)

    def collect(self):
        '''Collect share prices for symbols every collection_interval seconds
        and express them as Prometheus metrics'''
        share_prices = GaugeMetricFamily("share_price", "Last share price", labels=["symbol"])
        get_market_stack_last_share_price = GetMarketStackLastSharePrice(self.symbols,
                                                                         self.access_key)
        last_price_map = get_market_stack_last_share_price.get_last_price_map()
        for symbol in self.symbols:
            try:
                last_price = last_price_map[symbol]
                if last_price:
                    share_prices.add_metric([symbol], last_price)
                else:
                    logging.error("Last price is None for symbol {}, this is unexpected.".format(symbol))
            except KeyError:
                # Report loudly if we're missing a symbol but don't crash
                logging.exception("No last price data found for symbol {}, this is unexpected.".format(symbol))
        yield share_prices


def main():
    parser = argparse.ArgumentParser(description="Prometheus exporter for Dow Jones Industrial Average "
                                                 "component share prices")
    parser.add_argument("--collection-interval", type=int, nargs="?",
                        default=COLLECTION_INTERVAL_SECONDS_DEFAULT,
                        help="Frequency at which to update share prices, in seconds")
    parser.add_argument("--listen-port", type=int, nargs="?", default=LISTEN_PORT_DEFAULT,
                        help="The port that Prometheus will connect to and scrape metrics from")
    parser.add_argument("--log-level", type=str, nargs="?", choices=["NOTSET", "DEBUG", "INFO",
                                                                     "WARN", "ERROR", "CRITICAL"],
                        default="ERROR", help="Log level")
    args, unknown = parser.parse_known_args()
    if unknown:
        raise ValueError("Unknown arguments encountered - {}. Exiting".format(unknown))

    # Validate that we have an environment variable present for authenticating
    # to the market data source
    API_KEY = getenv("DATASOURCE_API_KEY")
    assert API_KEY, "Environment variable DATASOURCE_API_KEY is required to proceed. Exiting."

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=args.log_level,
                       format="%(asctime)s %(levelname)s %(message)s")
    SharePricePrometheusCollector(SYMBOLS, API_KEY, collection_interval=args.collection_interval,
                                  listen_port=args.listen_port)


if __name__ == "__main__":
    main()