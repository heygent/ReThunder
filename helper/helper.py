from typing import List

from infrastructure import Network
from protocol import MasterNode, SlaveNode


class SimulationHelper:

    def __init__(self, network: Network, master: MasterNode,
                 slaves: List[SlaveNode]):

        self.network = network = network or Network()
        self.netgraph = network.netgraph
        self.master = master
        self.slaves = slaves

    @classmethod
    def random(cls, num_of_slaves, **kwargs):
        raise NotImplementedError



