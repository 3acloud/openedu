class Task:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def s(self, *args, **kwargs):
        return (self, args, kwargs)


def task(func):
    return Task(func)


class Chain:
    def __init__(self, *tasks):
        self.tasks = tasks

    def __call__(self, initial_data):
        result = initial_data
        for task, args, kwargs in self.tasks:
            try:
                result = task(result, *args, **kwargs)
            except Exception as e:
                e.task_name = task.func.__name__
                raise e
        return result


def chain(*tasks):
    return Chain(*tasks)


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        if len(args) > 1:
            node_id = args[1]
        else:
            node_id = kwargs.get("node_id")
        print(f"{node_id} Function {func.__name__} took {elapsed_time} seconds to run.")
        if node_id is not None and isinstance(result, dict):
            if "node_run_time" not in result:
                result["node_run_time"] = {}
            result["node_run_time"][node_id] = elapsed_time
        return result

    return wrapper
