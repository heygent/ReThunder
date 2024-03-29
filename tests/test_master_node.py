import itertools
import random
import unittest

import networkx as nx

from infrastructure import Network
from protocol import MasterNode


def _addressing_is_wrong(tree, current, current_succ, father, father_succ):

    if father is not None and current < father:
        return True

    if father_succ is not None and current > father_succ:
        return True

    sorted_successors = tree.successors(current)
    sorted_successors.sort()

    for child, child_next, in itertools.zip_longest(
        sorted_successors, sorted_successors[1:]
    ):
        if _addressing_is_wrong(tree, child, child_next, current, current_succ):
            return True

    return False


def addressing_is_wrong(spaddrtree):
    return _addressing_is_wrong(spaddrtree, 0, None, None, None)


class MasterNodeTest(unittest.TestCase):

    def setUp(self):

        self.network = network = Network()
        self.master = master = MasterNode(network, lambda x, y, z: None)

        static_addr_graph = nx.Graph()

        it = itertools.count()
        static_addr_graph.add_path(next(it) for _ in range(10))

        for _ in range(2):
            for i in range(10):
                static_addr_graph.add_path(itertools.chain(
                    (i,), (next(it) for _ in range(5))
                ))

        for _ in range(2):
            for i in range(20):
                end_branch_addr = 10 + i * 5 - 1
                static_addr_graph.add_path(itertools.chain(
                    (end_branch_addr,), (next(it) for _ in range(5))
                ))

        master.init_from_static_addr_graph(static_addr_graph,
                                           assign_logic_addr=False)

    @unittest.skip
    def test_readdressing_algorithm(self):

        master = self.master

        address_pool = list(range(1, len(master.node_graph)))
        random.shuffle(address_pool)

        for node in master.node_graph:
            node.logic_address = None

        # sorted(master.node_graph, key=lambda x: x.static_address):
        for node in master.node_graph:
            if node.static_address == 0:
                node.logic_address = 0
            else:
                node.logic_address = address_pool.pop()

        master._update_sptree()
        master._readdress_nodes()

        # noinspection PyTypeChecker
        sptree = nx.relabel_nodes(master._sptree, lambda x: x.logic_address)
        self.assertFalse(addressing_is_wrong(sptree))

