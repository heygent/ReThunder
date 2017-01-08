from typing import List, Dict, Any

import networkx as nx


# noinspection PyPep8Naming
def shortest_paths_tree(shortest_paths: Dict[Any, List[Any]]):

    sptree = nx.DiGraph()

    for path in shortest_paths.values():
        sptree.add_path(path)

    if not nx.is_tree(sptree):
        raise ValueError("The graph resulting from adding all shortest_paths "
                         "is not a tree")
    return sptree


# noinspection PyPep8Naming
def preorder_tree_dfs(G: nx.DiGraph, start, action):

    action(start)
    for node in G.successors_iter(start):
        preorder_tree_dfs(G, node, action)
