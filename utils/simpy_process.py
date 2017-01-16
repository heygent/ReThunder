from functools import wraps


def as_generator(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if False:
            yield
        return fn(*args, **kwargs)

    return wrapper


def simpy_process(process_fn, env_attr='env'):

    @wraps(process_fn)
    def wrapper(self, *args, **kwargs):
        return getattr(self, env_attr).process(
            process_fn(self, *args, **kwargs)
        )

    return wrapper


def simpy_process_with_env(env_attr: str):
    return lambda fn: simpy_process(fn, env_attr)

