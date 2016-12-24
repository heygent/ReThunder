from functools import singledispatch
from typing import List

import simpy
import networkx as nx
from networkx.algorithms import bipartite

from infrastructure.bus import Bus
from protocol.master_node import MasterNode
from protocol.slave_node import SlaveNode


class BusPlaceholder:
    __slots__ = ['propagation_delay']

    def __init__(self, propagation_delay):
        self.propagation_delay = propagation_delay

    def __repr__(self):
        return f'BusPlaceholder(propagation_delay={self.propagation_delay})'


class SimulationHelper:

    def __init__(self, env, master, slaves):

        self.env = env
        self.master = master
        self.slaves = slaves

    @classmethod
    def from_graph(cls, network: nx.Graph, master_application,
                   slave_application=None, **kwargs):

        env = simpy.Environment()
        transmission_speed = kwargs.get('transmission_speed', 5)

        buses: List[Bus] = []

        @singledispatch
        def map_node(_):
            raise TypeError("The graph has a node of invalid type.")

        @map_node.register(BusPlaceholder)
        def _(placeholder):
            b = Bus(env, placeholder.propagation_delay)
            buses.append(b)
            return b

        @map_node.register(int)
        def _(static_addr):
            if static_addr == 0:
                return MasterNode(env, transmission_speed, master_application)
            else:
                return SlaveNode(env, transmission_speed, static_addr,
                                 application=slave_application)

        network_instances: nx.Graph = nx.relabel_nodes(network, map_node)

        if not bipartite.is_bipartite_node_set(network_instances, buses):
            raise ValueError('"network" is not bipartite.')

        for bus in buses:
            for node in network_instances.neighbors_iter(bus):
                bus.register_node(node)


