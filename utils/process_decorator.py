
def process(process_fn):

    def wrapper(self, *args, **kwargs):
        return self.env.process(process_fn(self, *args, **kwargs))

    return wrapper
