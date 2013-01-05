from types import FunctionType

# check if an object should be decorated
def do_decorate(attr, value):
    return ('__' not in attr and
        isinstance(value, FunctionType) and
        getattr(value, 'decorate', True))

# decorate all instance methods (unless excluded) with the same decorator
def decorate_all(decorator):
    class DecorateAll(type):
        def __new__(cls, name, bases, namespace):
            def gab(bases):
                nb = []
                for cls in bases:
                    nb.append(cls)
                    nb.extend(gab(cls.__bases__))
                return nb

            bases_namespaces = [base.__dict__.items() for base in gab(bases)]
            items = [item for sublist in bases_namespaces for item in sublist] + list(namespace.items())
            for attr, value in items:
                if do_decorate(attr, value):
                    namespace[attr] = decorator(value)
            return super(DecorateAll, cls).__new__(cls, name, bases, namespace)
        def __setattr__(self, attr, value):
            if do_decorate(attr, value):
                value = decorator(value)
            super(DecorateAll, self).__setattr__(attr, value)
    return DecorateAll

# decorator to exclude methods
def dont_decorate(f):
    f.decorate = False
    return f

