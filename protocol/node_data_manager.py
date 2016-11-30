import collections
import weakref

from sortedcontainers import SortedDict


class NodeDataManager(collections.Mapping):

    FLAG_VALUES = frozenset((None, -1))
    MAX_ADDRESS = 1 << 11

    class NodeData:

        def __init__(self, node_manager, static_address, logic_address=None):

            node_manager = weakref.proxy(node_manager)  # type: NodeDataManager

            self.__node_manager = node_manager
            self.__static_address = static_address
            self.__logic_address = None
            self.logic_address = logic_address
            self.current_logic_address = logic_address

            node_manager._on_create(self)

        @property
        def static_address(self):
            return self.__static_address

        @property
        def logic_address(self):
            return self.__logic_address

        @logic_address.setter
        def logic_address(self, logic_addr):
            self.__node_manager._map_to_logic(self, logic_addr)
            self.__logic_address = logic_addr

        def swap_logic_address(self, other):
            self.__logic_address, other.__logic_address = (
                other.__logic_address, self.__logic_address
            )
            self.__node_manager._swap_logic_mappings(
                self.__logic_address, other.__logic_address
            )

        def __eq__(self, other):
            return (self.static_address == other.static_address and
                    type(self) is type(other))

        def __hash__(self):
            return self.static_address

        def __repr__(self):
            return '<NodeData static={} logic={} current_logic={}>'.format(
                self.static_address, self.logic_address,
                self.current_logic_address
            )

    def __init__(self):
        self.__static_to_node = SortedDict()
        self.__logic_to_node = SortedDict()

    def __len__(self):
        return len(self.__static_to_node)

    def __iter__(self):
        return iter(self.__static_to_node)

    def __getitem__(self, item):
        return self.__static_to_node[item]

    def __delitem__(self, key):

        node = self.__static_to_node[key]
        del self.__static_to_node[key]

        if node.logic_address not in self.FLAG_VALUES:
            del self.__logic_to_node[node.logic_address]

    def from_logic_address(self, addr):
        return self.__logic_to_node[addr]

    def logic_addresses_iter(self):
        return sorted(self.__logic_to_node.keys())

    def _map_to_logic(self, node: NodeData, logic_address):

        logic_to_node = self.__logic_to_node

        old_logic_addr = logic_to_node.get(logic_address)

        if old_logic_addr is None:
            if logic_address not in self.FLAG_VALUES:
                logic_to_node[logic_address] = node
        elif logic_address in self.FLAG_VALUES:
            del logic_to_node[old_logic_addr]
        else:
            raise ValueError('The logic address is already assigned.')

    def _swap_logic_mappings(self, addr1, addr2):
        logic_to_node = self.__logic_to_node

        logic_to_node[addr1], logic_to_node[addr2] = (
            logic_to_node[addr2], logic_to_node[addr1]
        )

    def _on_create(self, node):
        if self.__static_to_node.get(node.static_address) is None:
            self.__static_to_node[node.static_address] = node
        else:
            raise ValueError('A node with the same static address already '
                             'exists.')

    def create(self, static_address=None, logic_address=None):
        return self.NodeData(self, static_address, logic_address)

    @classmethod
    def __get_free_address(cls, mydict: SortedDict):
        free_index = mydict.bisect_right(1)

        if free_index > cls.MAX_ADDRESS:
            raise ValueError('Maximum address limit reached.')

        return free_index

    def get_free_static_address(self):
        return self.__get_free_address(self.__static_to_node)

    def get_free_logic_address(self):
        return self.__get_free_address(self.__logic_to_node)
