from functools import wraps


def run_process(process_fn, env_attr='env'):

    @wraps(process_fn)
    def wrapper(self, *args):
        return getattr(self, env_attr).process(process_fn(self, *args))

    return wrapper


def run_process_with_env(env_attr: str):
    return lambda fn: run_process(fn, env_attr)

