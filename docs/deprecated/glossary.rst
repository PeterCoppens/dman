.. _glossary:

Glossary 
===================

We provide an overview of the concepts used within ``dman``. 
First some common terminology is defined. Then we show common examples 
on how to create objects that ``dman`` can handle. Afterwards we describe 
how file paths are determined in ``dman``, both with respect to the root of 
the file hierarchy and relative paths used within.

Terminology
-----------------------
When reading through ``dman`` documentation and code you will see the following 
terms occur frequently:

* ``serializable``: An object that can be turned into a ``json`` serializable type and back.
* ``storable``: An object that has a ``__write__`` and ``__read__`` method that enables storing tp and loading from a file.
* ``record``: Wraps a ``storable`` in a ``serializable`` type. Contains a pointer to the file when serialized.
* ``model``: Models extend standard python containers to support ``storable`` types.
  
     - ``modelclass`` extends a ``dataclass``.
     - ``mlist`` extends a ``list`` and ``smlist`` is its ``storable`` equivalent.
     - ``mdict`` extends a ``dict`` and ``smdict`` is its ``storable`` equivalent.
     - ``mruns`` acts like ``mlist`` but generates file names automatically (e.g. ``run-0``, ``run-1``, ...).

Creating Objects
-----------------------
When using ``dman`` you will tend to create objects in two main ways.
Either using a ``modelclass`` or using ``storables``. 
The first type extends a ``dataclass`` and supports storable types as fields.

.. code-block:: python

    @dman.modelclass(name='address')
    class Address:
        street: str
        number: int
        zip_code: int
        city: str
        country: str

The second is usually reserved for more complex object (e.g. ``dman.numeric.barray``)
and allows storing objects in files directly.

.. code-block:: python

    @dman.storable(name='person')
    class Person:
        __ext__ = '.person'   # specifies file extension (.sto by default)
        def __init__(self, name: str):
            self.name = name
        def __write__(self, path: str):
            with open(path, 'w') as f:
                f.write(self.name)
        @classmethod
        def __read__(cls, path: str):
            with open(path, 'r') as f:
                return cls(f.read())

.. note::

    A ``modelclass`` decorator can also be used to create ``storable``
    types. 

    .. code-block:: python

        @dman.modelclass(name='address', storable=True)


Saving and Loading
--------------------

We can save and load (or both) using ``save``, ``load`` and ``track``. 
To do so ``dman`` needs to determine the root of the file hierarchy.
This is always done in the same way based on the arguments passed
to the functions

.. code-block:: 

    <base>/<generator>/<subdir>/<key>/<key>.json    (cluster=True)
    <base>/<generator>/<subdir>/<key>.json          (cluster=False)

For a script located in ``<workspace>/examples/script.py``
the arguments have the following defaults 

- ``base``: ``<workspace>/.dman`` (``.dman`` should exist in a parent folder).
- ``generator``: ``cache/examples:script`` (path relative to ``.dman``).
- ``subdir``: ``''``

The ``key`` should always be provided and when ``cluster`` is 
n ``True`` a separate subfolder is created 'clustering' the files associated with the ``key``. Some examples are:

.. code-block:: python

    # <workspace>/.dman/cache/examples:script/fib/fib.json
    dman.save('fib', [1, 1, 2, 3, 5, 8])       
    # <workspace>/.dman/cache/examples:script/fib.json
    dman.save('fib', [1, 1, 2, 3, 5, 8], cluster=False)
    # <workspace>/.dman/example/fib.json
    dman.save('fib', [1, 1, 2, 3, 5, 8], generator='example')
    # /tmp/cache/examples:script/fib.json
    dman.save('fib', [1, 1, 2, 3, 5, 8], base='/tmp')


Targets
--------------

When the root of the file hierarchy is determined you 
can use a ``record`` to specify relative paths as follows:

.. code-block:: 

    <subdir>/<stem><suffix>   (using stem and/or suffix)
    <subdir>/<name>           (using name)

These arguments can be accessed directly when creating a ``record``:

.. code-block:: 

    # ./john.person
    dman.record(Person(name='John Silver'), stem='john')    
    dman.record(Person(name='John Silver'), stem='john', suffix='.person') 
    dman.record(Person(name='John Silver'), name='john.person')
    # ./people/john.person
    dman.record(Person(name='John Silver'), stem='john.person', subdir='people')

Since ``model`` types use a ``record`` internally you tend to be able to 
configure them manually:

.. code-block:: 

    # ./john.person
    dman.mdict().record('john', Person(name='John Silver'), stem='john')
    dman.mlist().record(Person(name='John Silver'), stem='john')
    dman.mlist([1, 2]).record(1, Person(name='John Silver'), stem='john')
    dman.mruns().record(1, Person(name='John Silver'), stem='john')

    @dman.modelclass
    class Individual:
        person: Person = dman.recordfield(stem='john')
        address: Address


Both ``mdict`` and ``mruns`` provide some options that can customize how 
records are created by default internally. 

.. code-block:: 

    # ./people/john/john.person
    dct = dman.mdict(subdir='people', store_by_key=True, store_subdir=True)
    dct['john'] = Person(name='John Silver')
    # ./john/52338792-bbeb-46fb-a90e-c3da6261b011.person
    dct = dman.mdict(store_by_key=False, store_subdir=True)
    # ./john.person
    dct = dman.mdict(store_by_key=True, store_subdir=False)

.. code-block:: 

    # ./people/employee-0/employee.person
    runs = dman.mruns(stem='employee', subdir='people', store_subdir=True)
    runs.append(Person(name='John Silver'))
    # ./employee-0.person
    runs = dman.mruns(stem='employee', store_subdir=False)
    runs.append(Person(name='John Silver'))

