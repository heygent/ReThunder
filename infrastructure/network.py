import logging
from typing import Dict

import networkx as nx
import simpy

from infrastructure import Bus


class Network:

    _logging_formatter = logging.Formatter(
        fmt="[{env.now:0>3}] {levelname} in {module}: {message}", style="{"
    )

    def __init__(self, env: simpy.Environment=None, netgraph: nx.Graph=None,
                 transmission_speed=5):

        self.env = env or simpy.Environment()
        self.netgraph = netgraph or nx.Graph()
        self.transmission_speed = transmission_speed

    def run_nodes_processes(self):
        for node in self.netgraph.nodes_iter():
            if hasattr(node, 'run_proc'):
                node.run_proc()

    def configure_log_handler(self, handler):

        handler.setFormatter(self._logging_formatter)

        env = self.env

        def env_filter(record):
            record.env = env
            return True

        handler.addFilter(env_filter)

    def configure_root_logger(self, **kwargs):

        logging.basicConfig(**kwargs)

        for handler in logging.getLogger().handlers:
            self.configure_log_handler(handler)

    def make_buses(self):

        netgraph = self.netgraph
        nodegraph_edges = netgraph.edges(data=True)
        netgraph.clear()

        for n1, n2, data in nodegraph_edges:
            prop_delay = data.get('propagation_delay', 10)
            bus = Bus(self, prop_delay)
            netgraph.add_star((bus, n1, n2))
