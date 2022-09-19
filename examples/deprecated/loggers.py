import dman
from dman import tui


def default():
    return dman.record(dman.log.LogTarget())

def main():
    with dman.track('log', default_factory=default, verbose=True) as rec:
        path = dman.get_directory('log')
        dman.remove(rec, context=dman.context(path))
        logger = dman.log.getLogger(None, level=dman.log.INFO)
        logger.addHandler(rec.content)
        dman.log.info('test')
    dman.log.info('more tests ...')

    tui.walk_directory(
        dman.get_directory(''), 
        show_content=True, 
        console=tui.Console(width=None)
    )

    tui.print('[red]test')



if __name__ == '__main__':
    main()