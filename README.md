# Dowmetheus

Dowmetheus is a small [Prometheus exporter](https://prometheus.io/docs/instrumenting/exporters/), implemented in Python3, which periodically collects share prices for Dow 30 components from [MarketStack](https://marketstack.com/documentation). With an accompanying [Prometheus monitoring server](https://prometheus.io), one can easily visualize price fluctuations throughout the day through a variety of frontends as well as alert on various conditions.

## Installation and Usage

Dowmetheus makes use of the [prometheus_client](https://github.com/prometheus/client_python) library, as well as [requests](https://pypi.org/project/requests/), and requires outbound internet access. An API key for MarketStack is also required, at [subscription level](https://marketstack.com/product) Basic or higher. The utility will expect this API key to be assigned to environment variable $DATASOURCE_API_KEY. Dowmetheus is expected to function with any minor version of Python3 on Linux, MacOS, or Windows, but has only been tested with Python3.10 on Ubuntu Linux 22.04. Example invocation:

```/bin/python3 main.py```

or simply

```./main.py```

The automated test suite can be run with the following command:

```/bin/python3 -m unittest -v main.py```

There are several configuration parameters exposed through the command line interface.

```./main.py --help
usage: main.py [-h] [--collection-interval [COLLECTION_INTERVAL]] [--listen-port [LISTEN_PORT]] [--log-level [{NOTSET,DEBUG,INFO,WARN,ERROR,CRITICAL}]]

Prometheus exporter for Dow Jones Industrial Average component share prices

options:
  -h, --help            show this help message and exit
  --collection-interval [COLLECTION_INTERVAL]
                        Frequency at which to update share prices, in seconds
  --listen-port [LISTEN_PORT]
                        The port that Prometheus will connect to and scrape metrics from
  --log-level [{NOTSET,DEBUG,INFO,WARN,ERROR,CRITICAL}]
                        Log level
```

## Related Infrastructure

For convenient demonstration, Prometheus server and [Grafana](https://grafana.com/) configuration files are provided in this repository.

### Prometheus

To run a Prometheus server that will ingest Dowmetheus' data in a local [Docker](https://www.docker.com/) container, run the following command in the root directory of this repository.

```docker run -d -p 9090:9090 --net=host -v "$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml" prom/prometheus --config.file="/etc/prometheus/prometheus.yml" --query.lookback-delta="15m"```

Note that this instruction assumes that you have successfully installed the Docker packages on your local machine, and that port 9090 is unoccupied.

### Grafana

To run a Grafana server pre-configured with a local Prometheus datasource and a rudimentary dashboard with the Dowmetheus time-series data, run the following command in the root directory of this repository.

```docker run -d -p 3000:3000 -v "$(pwd)/grafana/datasources/:/etc/grafana/provisioning/datasources/" -v "$(pwd)/grafana/dashboards/:/etc/grafana/provisioning/dashboards/" grafana/grafana-enterprise```

Like in Prometheus above, this instruction assumes that you have successfully installed the Docker packages on your local machine, and that port 3000 is unoccupied.
