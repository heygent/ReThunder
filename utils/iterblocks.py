from itertools import islice


def iterblocks(iterable, block_size, intersection_size=0):

    iters = [islice(iterable, i, None) for i in range(block_size)]
    return islice(zip(*iters), 0, None, block_size - intersection_size)
