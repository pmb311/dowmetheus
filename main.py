from abc import ABC, abstractmethod
from time import sleep

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

import argparse
import logging

COLLECTION_INTERVAL_SECONDS_DEFAULT=60
DOW_COMPONENTS = ("AAPL",
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
                  "V"
                  "VZ",
                  "WBA",
                  "WMT",
                  )
LISTEN_PORT_DEFAULT=9927

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
        sleep(self.collection_interval)
    
    @abstractmethod
    def collect(self):
        pass

class SharePricePrometheusCollector(PrometheusCollector):
    def __init__(self, **kwargs):
        super(SharePricePrometheusCollector, self).__init__(**kwargs)

    def collect(self):
        '''Collect share prices for DOW_COMPONENTS every collection_interval seconds and express them as Prometheus metrics'''
        share_prices = GaugeMetricFamily("share_price", "Current share price", labels=["symbol"])
        for component in DOW_COMPONENTS:
            # TODO dynamically update this from source data
            share_prices.add_metric([component], 50)
        yield share_prices


def main():
    parser = argparse.ArgumentParser(description="Prometheus exporter for Dow Jones Industrial Average component share prices")
    parser.add_argument("--collection-interval", type=int, nargs="?",
                        default=COLLECTION_INTERVAL_SECONDS_DEFAULT,
                        help="Frequency at which to update share prices, in seconds")
    parser.add_argument("--listen-port", type=int, nargs="?", default=LISTEN_PORT_DEFAULT,
                        help="The port that Prometheus will connect to and scrape metrics from")
    parser.add_argument("--log-level", type=str, nargs="?", choices=["NOTSET", "DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
                        default="ERROR", help="Log level")
    args, unknown = parser.parse_known_args()
    if unknown:
        raise ValueError("Unknown arguments encountered - {}. Exiting".format(unknown))

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=args.log_level,
                       format="%(asctime)s %(levelname)s %(message)s")
    SharePricePrometheusCollector(collection_interval=args.collection_interval,
                                  listen_port=args.listen_port)


if __name__ == "__main__":
    main()