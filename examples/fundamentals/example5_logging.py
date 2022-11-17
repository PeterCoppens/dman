"""
Logging
========================

We illustrate basic ``dman`` logging functionality.
"""

# %%
# When using ``dman`` you might have seen certain warning messages pop up,
# originating from the logger. This logger can be configured using :func:`dman.log.config`.

import dman

dman.log.config(level=dman.log.INFO)
dman.log.info("This is some info.")

# %%
# The syntax is similar to that of :func:`logging.basicConfig`.
#
# .. autofunction:: dman.log.config
#       :noindex:
#
# By default we use the :class:`RichHandler` from :class:`rich`. If you want
# to use more standard logging you can use the following configuration
dman.log.config(
    level=dman.log.INFO, use_rich=False, datefmt="%Y-%m-%d %H:%M:%S", force=True
)
dman.log.backend.basicConfig
dman.log.info("This is some info.")

# %%
# The ``dman`` logger also supports some additional functionality.
dman.log.config(level=dman.log.INFO, force=True, show_path=False)
with dman.log.layer("example", "layer", prefix="owner"):
    dman.log.info("Indented", label="example")
    dman.log.io("This is an io command", label="example")
    dman.log.emphasize("This is an emphasized command", label="example")

# %%
# It is also used extensively during saving, loading and other internal functionality.
_ = dman.save("person", {"name": "Adam", "age": 25, "position": [23, 12]})

# %%
# Since these logs can be quite verbose when you set the level to ``INFO``,
# it can be useful to save the file somewhere. In fact you can do so
# within the ``dman`` file tree.


@dman.modelclass
class Experiment:
    value: int
    log: dman.FileTarget = dman.recordfield(
        name="dman.log", default_factory=dman.FileTarget
    )


exp = Experiment(25)
dman.log.config(
    level=dman.log.INFO, stream=exp.log, force=True, console_style={"width": 160}
)
dman.clean("experiment", generator="")
dman.save("experiment", exp, generator="")
dman.tui.walk_directory(
    dman.mount("experiment", generator=""),
    show_content=True,
    console=dman.tui.Console(width=180),
)
