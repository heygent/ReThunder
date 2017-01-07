import logging
import simpy
import networkx as nx


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
