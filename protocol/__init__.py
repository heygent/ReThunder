from .master_node import MasterNode
from .slave_node import SlaveNode


def make_nodes(network, n, master_on_received=None, slave_on_received=None):

    nodes = [MasterNode(network, master_on_received)]
    # noinspection PyTypeChecker
    nodes.extend(SlaveNode(network, i, None, slave_on_received)
                 for i in range(1, n))
    return nodes
