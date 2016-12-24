import simpy
import networkx as nx


class Network:

    def __init__(self, env: simpy.Environment=None, netgraph: nx.Graph=None,
                 transmission_speed: int=5):

        self.env = env or simpy.Environment()
        self.netgraph = netgraph or nx.Graph()
        self.transmission_speed = transmission_speed
