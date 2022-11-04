"""
TUI plugin
-----------------

The ``tui`` (terminal user interface) is a minimal wrapper around ``rich``,
which is a dependency of the plugin.

"""

from dman import tui
import time


def main():
    state = (3, 2, 0)
    stack = tui.TaskStack(state=state)
    task0 = stack.register('task.i.i | [{i:02}/10]', 10, {'i': 0})
    task1 = stack.register('task.i   | [{j:02}/3]', 3, {'j': 0})
    task2 = stack.register('task     | [{k:02}/5]', 5, {'k': 0})

    n = 1
    for k, j, i in stack:
        stack.update(task0, i=i+1)
        stack.update(task1, j=j+1)
        stack.update(task2, k=k+1)
        time.sleep(0.01)
        n+= 1
        if (k, j, i) == state:
            n = 2
    print(n)

    tui.walk_directory('.dman', show_content=True)


if __name__ == '__main__':
    main()