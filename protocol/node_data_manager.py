import collections
import weakref

from sortedcontainers import SortedDict


class NodeDataManager(collections.Mapping):

    FLAG_VALUES = frozenset((None,))
    MAX_ADDRESS = 1 << 11 - 1

    class NodeData:

        def __init__(self, node_manager, static_address=None,
                     logic_address=None):

            node_manager = weakref.proxy(node_manager)  # type: NodeDataManager

            self._node_manager = node_manager
            self._static_address = (
                static_address or node_manager.get_free_static_address()
            )
            self._logic_address = None
            self.logic_address = logic_address
            self.current_logic_address = None

            node_manager._on_create(self)

        @property
        def static_address(self):
            return self._static_address

        @property
        def logic_address(self):
            return self._logic_address

        @logic_address.setter
        def logic_address(self, logic_addr):
            self._node_manager._map_to_logic(self, logic_addr)
            self._logic_address = logic_addr

        def swap_logic_address(self, other):

            self._logic_address, other._logic_address = (
                other._logic_address, self._logic_address
            )
            self._node_manager._swap_logic_mappings(
                self._logic_address, other._logic_address
            )

        def __repr__(self):
            return '<NodeData static={} logic={} current_logic={}>'.format(
                self.static_address, self.logic_address,
                self.current_logic_address
            )

    def __init__(self):
        self._static_to_node = SortedDict()
        self._logic_to_node = SortedDict()

    def __len__(self):
        return len(self._static_to_node)

    def __iter__(self):
        return iter(self._static_to_node)

    def __getitem__(self, item: int) -> NodeData:
        return self._static_to_node[item]

    def __delitem__(self, key):

        node = self._static_to_node[key]
        del self._static_to_node[key]

        if node.logic_address not in self.FLAG_VALUES:
            del self._logic_to_node[node.logic_address]

    def from_logic_address(self, addr: int) -> NodeData:
        return self._logic_to_node[addr]

    def logic_addresses_view(self):
        return self._logic_to_node.keys()

    def _map_to_logic(self, node: NodeData, new_logic_address):

        logic_to_node = self._logic_to_node

        invalid_previous_addr = node.logic_address in self.FLAG_VALUES
        only_delete = new_logic_address in self.FLAG_VALUES
        already_assigned = (
            logic_to_node.get(new_logic_address, self) is not self
        )

        if already_assigned:
            raise ValueError('The logic address is already assigned.')

        if not invalid_previous_addr:
            del logic_to_node[node.logic_address]
        if not only_delete:
            logic_to_node[new_logic_address] = node

    def _swap_logic_mappings(self, addr1, addr2):
        logic_to_node = self._logic_to_node

        logic_to_node[addr1], logic_to_node[addr2] = (
            logic_to_node[addr2], logic_to_node[addr1]
        )

    def _on_create(self, node):
        if self._static_to_node.get(node.static_address) is None:
            self._static_to_node[node.static_address] = node
        else:
            raise ValueError('A node with static address {} already '
                             'exists.'.format(node.static_address))

    def create(self, static_address=None, logic_address=None):
        return self.NodeData(self, static_address, logic_address)

    @classmethod
    def _get_free_address(cls, mydict: SortedDict):
        free_index = mydict.bisect_right(1)

        if free_index > cls.MAX_ADDRESS:
            raise ValueError('Maximum address limit reached.')

        return free_index

    def get_free_static_address(self) -> int:
        return self._get_free_address(self._static_to_node)

    def get_free_logic_address(self) -> int:
        return self._get_free_address(self._logic_to_node)

NodeDataT = NodeDataManager.NodeData
