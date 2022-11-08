"""
Mounting and Targets
========================

To keep track of files internally ``dman`` has some custom path specifications.
"""

# %%
# Introduction
# ---------------------------
# 
# Internally ``dman`` specifies paths through mount points and targets.
# A mount point determines the root of the file tree that is constructed during 
# serialization, while targets are used to specify the positions of files 
# within this tree defined relative to the current directory. 
#
# We will operate in a temporary directory for the purpose of this example.
# To do so we need to make sure it contains a ``.dman`` subfolder. Usually 
# you can create one by executing ``dman init`` in your terminal. We 
# do so using :func:`get_root_path` here.

import os, subprocess, textwrap
import dman
from tempfile import TemporaryDirectory

# Create a temporary directory and change our directory to it.
tmp = TemporaryDirectory()
os.chdir(tmp.name)

# Create the ``.dman`` folder.
# This is identical to calling ``dman init`` in terminal.
dman.get_root_path(create=True)  

# %%
# Mount points
# ----------------------------
# We begin with introducing mount points. The signature of the :func:`dman.mount`
# method will appear often when using ``dman`` so we begin with discussing
# it in detail, before showing other functionalities provided by mount points.
#
# Initialization
# ^^^^^^^^^^^^^^^^^^^
# 
# A mount point is specified from some base directory, which usually 
# is a ``.dman`` folder, located above the current working directory
# in the file tree (similarly to how a ``.git`` folder is located). 
# For the purposes of this example we use the temporary directory created above.

os.chdir(tmp.name)
print(dman.mount('object'))

# %%
# We can break up the path into three parts.
#
# - ``<temporary dir>/.dman``` is the base directory, outputted by :func:`get_root_path`.
# - ``cache/example4_path``` is referred to as the generator.
# - ``object``` is the key of the specific file tree being operated on. 
# 
# These match the arguments of :func:`mount`. 
#
# .. autofunction:: dman.mount
#
# The most complex argument is the ``generator``. 
# Usually this is based on the path of the script relative to the root path
# containing ``.dman``. We can illustrate this by first creating a script 
# local to the temporary directory. 

# Create script that prints the evaluation mount.
os.chdir(tmp.name)
os.mkdir(os.path.join(tmp.name, 'scripts'))
local = os.path.join(tmp.name, 'scripts', 'script.py')
content = '''
import dman
print(dman.mount('object'))
'''
with open(local, 'w') as f:
    f.write(content)

# We can then see what the new output of ``mount`` is.
out = subprocess.check_output(f'python {local}', shell=True)
print(str(out, 'utf-8'))

# %%
# The other arguments are relatively straightforward. 
# We provide some examples below

os.chdir(tmp.name)
print('generator ...', dman.mount('object', generator='gen'))
print('base ........', dman.mount('object', base=os.path.join('home', 'user')))
print('subdir ......', dman.mount('object', subdir='folder'))
print('cluster .....', dman.mount('object', cluster=False))

# %%
# The final example, involving ``cluster``, does not include the key
# and is thus equivalent to 

os.chdir(tmp.name)
print('cluster .....', dman.mount(''))

# %%
# The reason for this redundancy is to be consistent with ``save``, ``load`` 
# and ``track``. There the ``key`` determines the file name and the default
# ``cluster=True`` means a dedicated directory is created for the file tree.

# %%
# File IO
# ^^^^^^^^^^^^^^^^^^
#
# Next we show how ``mount`` can be used to edit and remove files automatically.
os.chdir(tmp.name)
mnt = dman.mount('object', cluster=False)
print(mnt)

# Write some text to a file.
with mnt.open('howto.txt', 'w') as f:
    f.write(textwrap.dedent("""
        This is a book of bad ideas.
            At least, most of them are bad ideas. It's possible some 
        good ones slipped through the cracks. If so, I apologize.
    """))

# %%
# One useful feature of mount points is that they detect when files have 
# been written to before. For example:
with mnt.open('howto.txt', 'w') as f:
    f.write(textwrap.dedent("""
        This information was lost.
    """))

# %%
# By default a warning is provided, but we can also raise an error
from dman.core.path import UserQuitException
try:
    # set retouch action
    dman.params.store.on_retouch = 'quit' 

    with mnt.open('howto.txt', 'w') as f:
        f.write(textwrap.dedent("""
            This string will never be written.
        """))
except UserQuitException as e:
    print(e)

# %%
# Alternatively we can automatically increment the file name.
dman.params.store.on_retouch = 'auto'

with mnt.open('howto.txt', 'w') as f:
    f.write(textwrap.dedent("""
        This is a book of bad ideas.
            At least, most of them are bad ideas. It's possible some 
        good ones slipped through the cracks. If so, I apologize.
    """))

# %%
# You can also configure ``dman`` to prompt the user as follows:
#
# .. code-block:: python
#
#       dman.params.store.on_retouch = 'prompt'
# 
# And the default behavior can be recovered using:
#
# .. code-block:: python
#
#       dman.params.store.on_retouch = 'ignore'
# 

# %%
# The final state of the 
mnt.close()
dman.tui.walk_directory(mnt, show_content=True, show_hidden=True)

# %%
# Note that the edited files are also added to a ``.gitignore`` file 
# automatically. You can add ``gitignore=False`` to your call of ``mnt``
# to avoid this. 
#
# We can also remove files and they are removed from the ``.gitignore``
# automatically. 
mnt.remove('howto.txt')
mnt.close()
dman.tui.walk_directory(mnt, show_content=True, show_hidden=True)


# %%
# Targets
# ---------------
#
# For now we have been specifying paths relative to the mount point 
# using strings. Internally ``dman`` used ``target`` to create these 
# paths. It is useful to know about this since many higher-level methods
# use the same signature.
#
# .. autofunction:: dman.target
#
# We provide some examples here

print('a.', dman.target(stem='file', suffix='.obj'))
print('b.', dman.target(name='file.obj'))
print('c.', dman.target(name='file.obj', subdir='folder'))