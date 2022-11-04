import dman
from dman import tui


class Broken:
    ...


@dman.modelclass
class Content:
    log: dman.log.LogTarget = dman.recordfield(default_factory=dman.log.LogTarget)
    content: Broken = dman.field(default_factory=Broken)


def default():
    return Content()


def main():
    # dman.log.basicConfig(level=dman.log.WARNING)
    with dman.track("log", default_factory=default, verbose=False) as content:
        content: Content = content
        dman.remove(content, context=dman.Context.mount('log'))
        logger = dman.log.getLogger(level=dman.log.INFO)
        logger.addHandler(content.log)
        dman.log.info("test")
    dman.log.info("more tests ...")

    tui.walk_directory(
        dman.mount(""),
        show_content=True,
        console=tui.Console(width=None, theme=dman.log.log_theme),
    )

    # tail log target
    target = dman.log.LogTarget()
    logger = dman.log.getLogger("trailing", level=dman.log.INFO)
    logger.addHandler(target)
    logger.info("test")

    tui.walk_directory(
        target.tempdir.name,
        show_content=True,
        console=tui.Console(width=None, theme=dman.log.log_theme),
    )

    # the unresolved log targets are removed after the script quits.


if __name__ == "__main__":
    main()
