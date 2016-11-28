import networkx as nx


# noinspection PyPep8Naming
def shortest_paths_tree(G: nx.Graph, source, weight='weight'):

    shortest_paths = nx.shortest_path(G, source=source, weight=weight)
    sptree = nx.DiGraph()

    for path in shortest_paths.values():
        sptree.add_path(path)
        assert nx.is_tree(G)

    return sptree


# noinspection PyPep8Naming
def preorder_tree_dfs(G: nx.DiGraph, start, action):

    action(start)
    for node in G.successors_iter(start):
        preorder_tree_dfs(G, node, action)
