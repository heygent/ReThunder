from .iterblocks import iterblocks
import networkx as nx
import itertools


# noinspection PyPep8Naming
def shortest_paths_tree(G: nx.Graph, source, weight='weight'):

    shortest_paths = nx.shortest_path(G, source=source, weight=weight)
    edges_iters = [iterblocks(path, 2, 1) for path in shortest_paths.values()]
    edges = {(u, v, G[u][v][weight]) for u, v in itertools.chain(*edges_iters)}

    ret = nx.Graph()
    ret.add_weighted_edges_from(edges, weight=weight)
    return ret
