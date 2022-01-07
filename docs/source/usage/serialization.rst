.. _fundamentals:


The Fundamentals
================================
.. include:: ../definitions.rst

The |pylib_name| package is implemented in a hierarchical fashion.
The base levels are ``serializables`` and ``storables``, on which 
more advanced functions like ``record`` and ``modelclass`` 
objects are built. 



Serializables
------------------
The base objects are ``serializables``. Any ``serializable`` instance 
is defined such that the following operation results an instance of the same state. 

.. code-block:: python

    from dman import sjson, serialize, deserialize

    # let obj be a serializable object
    ser: dict = serialize(obj)
    res: str = sjson.dumps(serialized)
    ser: dict = sjson.loads(serialized)
    result = deserialize(ser)


.. note::
    We used ``sjson`` instead of ``json`` for dumping the dictionary
    to a string. This replaces any unserializable objects with 
    a placeholder string. This corresponds with the ideals behind ``dman``,
    one of which is that (some) serialization should always be produced. 


The goal is that the string ``res`` can be stored in a (human-readable) file. 

By default, all types that can be handled by ``json`` are considered serializable.
Specifically: ``str``, ``int``, ``float``, ``bool``, ``NoneType``, ``list``, ``dict``, ``tuple``.
Collections can be nested.  
Note that ``tuple`` is somewhat of an exception, since it is deserialized as a list. 

We extend upon this base ``json`` layer by also enabling the creation of custom
serializable objects. These can be created as follows

.. code-block:: python

    from dman import serializable

    @serializable(name='manual')
    class Manual:
        def __init__(self, value: str):
            self.value = value

        def __serialize__(self):
            return {'value': self.value}
        
        @classmethod
        def __deserialize__(cls, ser: dict):
            return cls(ser.get('value', None))

The ``serializable`` decorator registers the class as a serializable type. 
These are expected to have two methods. The ``__serialize__`` method 
should store all values defining an instance of a class in a dictionary. 
This dictionary should, to be compatible with other modules in ``dman`` be
json serializable. The ``__deserialize__`` method then turns the dictionary
back into an instance. 

We can use our ``serialize`` our ``serializable`` class

.. code-block:: python

    from dman import serialize, sjson

    test = Manual(value='hello world!')
    ser = serialize(test)
    print(sjson.dumps(ser, indent=4))

The output is then

.. code-block:: json

    {
        "_ser__type": "manual",
        "_ser__content": {
            "value": "hello world!"
        }
    }

Note how the dictionary under ``_ser__content`` is the output of our ``__serialize__``
method. The type name is also added such that the dictionary can be interpreted
correctly. We can ``deserialize`` a dictionary created like this as follows:

.. code-block:: python

    from dman import deserialize
    reconstructed: Manual = deserialize(ser)

.. note::
    It is possible to not include the serializable type and deserialize
    by specifying the type manually using the following syntax

    .. code-block:: python

        ser = serialize(test, content_only=True)
        reconstructed: Manual = deserialize(ser, ser_type=Manual)

Of course it would not be convenient to manually specify the ``__serialize__``
and ``__deserialize__`` methods. Hence, the ``serializable`` decorator
has been implemented to automatically generate them whenever 
the class is a ``dataclass`` (and when no prior ``__serialize__``
and ``__deserialize__`` methods are specified). 

.. code-block:: python

    from dataclasses import dataclass

    @serializable(name='dcl_basic')
    @dataclass
    class DCLBasic:
        value: str

    test = DCLBasic(value='hello world!')
    ser = serialize(test)
    print(sjson.dumps(ser, indent=4))

Produces similar output to before

.. code-block:: json

    {
        "_ser__type": "dcl_basic",
        "_ser__content": {
            "value": "hello world!"
        }
    }

As long as all of the fields in the dataclass are serializable, the whole
will be as well. 

.. warning::

    Be careful when specifying the name that it is unique. It 
    is used to reconstruct an instance of a class based on the 
    ``_ser__type`` string. If a name is left unspecified, the value 
    under ``__name__`` in the class will be used.


.. note::

    It is possible to have fields in your dataclass that you don't 
    want serialized. ''

    .. code-block:: python

        from dataclasses import dataclass

        @serializable(name='dcl_basic')
        @dataclass
        class DCLBasic:
            __no_serialize__ = ['hidden']
            value: str
            hidden: int = 0

    The field names in ``__no_serialize__`` will not be included 
    in the serialized ``dict``. Note that this means that you should
    specify a default value for these fields to support deserialization.



Storeables
----------------------
Sometimes it is impossible to serialize an object. For example large 
arrays in ``numpy``. The ``dman`` framework supports such objects through 
``storables``. These should interface with the ``read`` and ``write``
similarly to how ``serializables`` interface with ``serialize`` and ``deserialize``.

.. code-block:: python

    from dman import read, write

    # let obj be a storable object=
    write(obj, 'obj.out')
    result = read(type(obj), 'obj.out')


By default no objects are storable. They should be defined by the user as 
follows.

.. _manual-file-def:

.. code-block:: python

    from dman import storable

    @storable(name='manual')
    class ManualFile:
        def __init__(self, value: str):
            self.value = value
        
        def __write__(self, path: str):
            with open(path, 'w') as f:
                f.write(self.value)
        
        @classmethod
        def __read__(cls, path: str):
            with open(path, 'r') as f:
                value = f.read()
                return cls(value)


.. warning::

    Again, the specified name should be unique for all storables.
    It can be the same as a name of a serializable object. A name can 
    also be automatically generated similar to ``serializable`` when it is left unspecified.
    The name can be used instead of the type when reading, which is used by the 
    more complex objects in ``dman``. 

    .. code-block:: python

        write(ManualFile(value='test'), 'obj.out')
        result = read('manual', 'obj.out')


It is also possible to automatically produce storables from 
dataclasses or serializable objects. With both json is used to 
store the object, however with a dataclass we use the default ``asdict``
method to convert it to a dictionary, which only works for certain types of fields.


.. code-block:: python

    from dman import storable, serializable, dataclass

    @storable(name='manual')
    @dataclass
    class DCLBasic:
        value: str

    @storable(name='manual')
    @serializable(name='manual')
    @dataclass
    class SerBasic:
        value: str


.. note::

    It is not recommended to create storables from dataclasses as above. 
    Instead one should use the more powerful ``modelclass`` decorator
    with ``storable=True`` as introduced below. The reason is that ``modelclass`` supports 
    storables as fields, where this method does not. 


Records
---------------------
We have introduced ``storables`` and ``serializables``. The first are however less 
flexible. Ideally we would want to store them in containers like dicts, 
lists and dataclasses. After all, if we just wanted to save an object to 
a file we could do so manually just as easily. The power of ``storables``
is increased significantly by interfacing them with the ``serializables``
framework. This interface is a ``record``: a serializable wrapper for
a ``storable``. Such a ``record`` has a the following features:

* File names and extensions can be specified manually or created automatically.
* Sub folders can be specified.
* Reading the object from file can be delayed until the content is accessed. 

We will first show a basic use-case before going into details. We will be using 
the ``ManualFile`` class specified earlier :ref:`here <manual-file-def>`.

.. code-block:: python

    from dman import record, serialize, sjson, record_context
    from tempfile import TemporaryDirectory

    instance = ManualFile(value='hello world!')
    rec = record(instance)

    with TemporaryDirectory() as base:
        ctx = record_context(base)
        ser = serialize(rec, context=ctx)
        
        # show the serialization
        print(sjson.dumps(ser, indent=4))

        # list existing files
        list_files(base)

        # deserialize record
        res = deserialize(ser, ctx)
        print('record: ', res)

        # load the content
        content: ManualFile = res.content
        print('content: ', content.value)
        print('record: ', res)

We will go through the process step by step. 
Note that we call serialize using ``serialize(rec, content=ctx)``,
which passes the ``record_context`` to the serialization process.
This context is used by the record to determine the folder where 
its content should be stored. 

When the record is serialized, a file name is picked (using ``uuid4``,
since no name was specified). The serialization then contains all 
information required to recover the content of the record:

.. code-block:: json

    {
        "_ser__type": "_ser__record",
        "_ser__content": {
            "target": "fb2ec913-0a1f-4ba3-8b14-98ab710066fd",
            "sto_type": "manual"
        }
    }

Specifically you can find that the name specified when creating 
the ``storable`` was recorded. Moreover a ``stem`` field is specified. 
Listing the contents of the ``base`` directory shows that this specifies the file name.


.. code-block:: text

    file tree of /tmp/tmpvkjxdso0
    >>> fb2ec913-0a1f-4ba3-8b14-98ab710066fd

    contents of /tmp/tmpvkjxdso0/fb2ec913-0a1f-4ba3-8b14-98ab710066fd
    >>> hello world!

Printing the result of the deserialization results in 


.. code-block:: text

    record:   Record(UL[manual], target=feb6da34-2d33-4fbf-afac-4eaf41e34154)

We can see that the content is still unloaded from ``UL[manual]``. 
Loading the ``content`` gives the following result:


.. code-block:: text

    content:  hello world!
    record:   Record(manual, target=feb6da34-2d33-4fbf-afac-4eaf41e34154)


We can see that the value is correctly loaded and that the ``record``
now no longer has an ``UL`` flag. So it will not load the file again 
when the content is accessed again. 

To give an overview of the options available when creating 
a record we provide its documentation:


.. autofunction:: dman.record
    :noindex:


The way file names are specified is left flexible for internal use, 
but is hence somewhat complex. We list examples below.

================================================       =========================
options                                                 target
================================================       =========================
``stem='test'``                                         ``./test``
``stem='test', suffix='.txt'``                          ``./test.txt``
``name='test.txt'``                                     ``./test.txt``
``name='test.txt', subdir='dir'``                       ``./dir/test.txt``
``name='test.txt', stem='test', suffix='.txt'``         ``ValueError``
================================================       =========================

.. note::
    It is also possible to automatically determine the ``suffix`` based 
    on the class.


    .. code-block:: python

        @storable(name='manual')
        class ManualFile:
            __ext__ = '.obj'
            ...


    So if only a ``stem=test`` is specified the target will automatically become ``test.obj``. 
    If a ``suffix`` is specified anyway, then the one specified through ``__ext__`` 
    is overridden. 

    When a ``storable`` is automatically created from a ``dataclass`` or a ``serializable``
    the ``suffix`` will be set to ``.json`` by default. 


.. warning::
    Be careful specifying the ``stem`` of a file. It usually makes sense
    to omit it and leave the selection up to the ``record``. That way you
    will not accidentally re-use existing files. 

.. note::

    The ``dman.remove`` method supports deletion of the file(s) associated 
    with a ``record``. A ``context`` needs to be provided to allow evaluation 
    of the pointers registered in the ``record``. 

Model Containers
--------------------------------
Leveraging the ``record`` it becomes possible to create the more powerful
container types. The ``mlist``, ``mdict`` and ``modelclass``. These
can be nested into each other as with the normal serializable equivalents. 
They are however more powerful since they can also contain ``storables``. 
This is implemented through the ``record`` system, in that 
they are not preloaded by default and filenames can be allocated automatically. 
This all is hidden from the user and the interface is the same 
as for usual lists, dictionaries and dataclasses. Only once you index 
a field containing a ``storable`` will it be loaded and then cached for
further use. 

Model List
^^^^^^^^^^^^^

Let us begin with the ``mlist`` container. We again will be using the 
``ManualFile`` class specified :ref:`here <manual-file-def>`.

.. code-block:: python

    from dman import mlist, serialize, deserialize, sjson
    from dman import record_context
    from dman.utils.display import list_files
    from tempfile import TemporaryDirectory

    lst = mlist()
    lst.append('value')
    lst.append(ManualFile(value='hello world!'))

    with TemporaryDirectory() as base:
        ctx = record_context(base)
        ser = serialize(lst, ctx)

        print(sjson.dumps(ser, indent=4))
        list_files(base)

The serialization looks like this

.. code-block:: json

    {
        "_ser__type": "_ser__mlist",
        "_ser__content": {
            "store": [
                "value",
                {
                    "_ser__type": "_ser__record",
                    "_ser__content": {
                        "target": "c9c3cdb7-01f6-4ea6-87cd-e617273c0885",
                        "sto_type": "manual"
                    }
                }
            ]
        }
    }

We can observe that ``store`` contains the string and then a dictionary,
with specified type ``_ser__record``. As discussed in the introduction,
the cause is that a ``storable`` is automatically wrapped inside of 
a record when added to the list. This record then contains a pointer 
to a file, which we can see in the file tree

.. code-block:: text
    
    file tree of /tmp/tmplcffojpx
    >>> 930be22e-d120-4ae9-a3ca-bb4a31e3980e

    contents of /tmp/tmplcffojpx/930be22e-d120-4ae9-a3ca-bb4a31e3980e
    >>> hello world!

We can access the record as follows:

.. code-block:: python

    rec = lst.store[1]

When deserializing the ``mlist`` again and printing the value of the record
we see

.. code-block:: python

    res = deserialize(ser, ctx)
    print(res.store[1])     # Record(UL[manual], target=930be22e-d120-4ae9-a3ca-bb4a31e3980e)
   

The content is still unloaded. Accessing the element in the list 
will load the content automatically.

.. code-block:: python

    print(res[1].value)     # hello world!
    print(res.store[1])     # Record(manual, target=8a9fa9b2-f0d7-4d56-ad6c-3d80686bc72c)

Interfacing with the list happens like normal and everything is handled
automatically behind the scenes. Even deleting works, but the files are only 
deleted when the ``mlist`` is serialized again (since the list 
does not know what context it has been serialized in before). 

As we saw earlier the ``record`` method has several options, like 
specifying file names, suffixes and sub-folders. We enable specifying 
these at two layers. First the ``mlist`` has a default record configuration,
which is specified during initialization

.. autofunction:: dman.mlist.__init__
    :noindex:

So we can specify a ``subdir`` and whether to ``preload`` storables. 
The option of specifying file names at this level is not provided, 
since then multiple records will always point to the same file. 

If you do want to specify a filename you can do so by using the 
``record`` method of the list (which acts like ``append`` or ``insert``
depending on whether an index is passed).

.. autofunction:: dman.mlist.record
    :noindex:

We can also pass a ``subdir`` at this level, which is appended
value of ``subdir`` set during initialization (which is ``'.''`` by default). 
Similarly we can again specify whether to ``preload`` the value.
Now the ``stem`` and ``suffix`` or ``name`` can also be specified. 

So, below you can find an example giving an overview of these features

.. code-block:: python 

    lst = mlist([1, 2], subdir='lst', preload=False, auto_clean=True)
    lst.append(ManualFile(value='stored in lst'))
    lst.record(ManualFile(value='stored in root'), subdir='../')
    lst.record(ManualFile(value='preloaded'), preload=True)

You can repeat the steps from before the examine how the list is serialized. 

.. note:: 

    The ``mlist`` also supports item deletion (either through ``pop`` or ``del``). 
    The files associated with the deleted record will be removed 
    when the ``mlist`` is serialized again. You can access the records scheduled 
    for removal by using ``lst.unused``. 

    To clean the contents of the list you can use 
    
    .. code-block:: python

        lst.clear()
        serialize(lst, ctx)
    
    Specifically ``clear`` schedules all records in the ``mlist`` for removal.
    When we serialize, the files are then actually removed.


Model Dictionary 
^^^^^^^^^^^^^^^^^^^

The ``mdict`` container extends the classical ``dict`` and can contain 
``storable`` types. The syntax is similar to that of ``mlist``. 
We again will be using the ``ManualFile`` class specified :ref:`here <manual-file-def>`.

.. code-block:: python

    from dman import mdict, serialize, sjson
    from dman import record_context
    from dman.utils.display import list_files
    from tempfile import TemporaryDirectory

    dct = mdict()
    dct['key'] = 'value'
    dct['manual'] = ManualFile(value='hello world!')

    with TemporaryDirectory() as base:
        ctx = record_context(base)
        ser = serialize(dct, ctx)

        print(sjson.dumps(ser, indent=4))
        list_files(base)


The serialization looks like this

.. code-block:: json

    {
        "_ser__type": "_ser__mdict",
        "_ser__content": {
            "store": {
                "key": "value",
                "manual": {
                    "_ser__type": "_ser__record",
                    "_ser__content": {
                        "target": "e55aa3df-c3fd-408d-861d-b77015280382",
                        "sto_type": "manual"
                    }
                }
            }
        }
    }

Similar to ``mlist``, ``store`` contains the string and then a dictionary,
with specified type ``_ser__record``. It provides a pointer to the 
file. The output of ``list_files`` is then:

.. code-block:: text
    
    file tree of /tmp/tmpr6yrk1gv
    >>> e55aa3df-c3fd-408d-861d-b77015280382

    contents of /tmp/tmpr6yrk1gv/e55aa3df-c3fd-408d-861d-b77015280382
    >>> hello world!

We can access the record as follows:

.. code-block:: python

    rec = dct.store['manual']

The loading behavior is analogous to the behavior for ``mlist``. 
The additional options for initializing an ``mdict`` however slightly differ.

.. autofunction:: dman.mdict.__init__
    :noindex:

We again have the option to set a ``subdir`` and to specify whether 
values should be preloaded through ``preload``. Two other options are provided:
``store_by_key`` and ``store_subdir``. These influence the place 
where files are stored. We list all cases below for the ``mdict`` created 
above. 

+--------------------------+--------------------------+---------------------------+
|                          | ``store_by_key == True`` | ``store_by_key == False`` |
+--------------------------+--------------------------+---------------------------+
| ``store_subdir == True`` | <base>/manual/manual     | <base>/manual/<uuid4>     |
+--------------------------+--------------------------+---------------------------+
| ``store_subdir == False``| <base>/manual            | <base>/<uuid4>            |
+--------------------------+--------------------------+---------------------------+

Here, ``<base>`` denotes the directory specified in the ``record_context``
and ``<uuid4>`` depicts a unique automatic file name (e.g. ``e55aa3df-c3fd-408d-861d-b77015280382`` as above).
Note that, if we additionally set ``subdir='test'`` then the effect of 
the options are stacked. For example the top-left cell would 
become ``<base>/test/manual/manual``. 

All of these options can be overridden using the ``record`` method as with ``mlist``.
We list the documentation below for completeness sake. Note that the value of ``subdir``
passed there is also stacked. So continuing the example above, 
``record(..., subdir='end')`` gives ``<base>/test/manual/manual/end``. 

.. autofunction:: dman.mdict.record
    :noindex:

The options are mostly analogous to those for ``mlist.record``. 

.. note:: 
    
    The ``mdict`` also supports item deletion through ``del``.
    Similarly to how it worked for ``mlist``, the files associated with the 
    deleted record will be removed when the ``mdict`` is serialized again. 
    When a key previously containing a record is overridden, then 
    the old record will similarly be scheduled for removal. The records
    scheduled for removal are stored in ``dct.unused``. 

    Similarly to ``mlist``, ``mdict`` also has a ``clear`` method. 


Model Classes
^^^^^^^^^^^^^^^

We finally consider a generalization of a serializable ``dataclass``
that has ``storable`` types as fields. 

We can define a ``modelclass`` as follows:

.. code-block:: python

    from dman import modelclass, record_context, serialize, sjson
    from tempfile import TemporaryDirectory

    @modelclass(name='model')
    class Model:
        name: str
        content: ManualFile

    with TemporaryDirectory() as base:
        ctx = record_context(base)
        model = Model(name='test', content=ManualFile(value='hello world!'))
        ser = serialize(model, ctx)
        print(sjson.dumps(ser, indent=4))

The serialization then looks as follows

.. code-block:: json

    {
        "_ser__type": "model",
        "_ser__content": {
            "name": "test",
            "content": {
                "_ser__type": "_ser__record",
                "_ser__content": {
                    "target": "1a3c0e93-f20d-438f-a6dc-b23acdde5202",
                    "sto_type": "manual"
                }
            }
        }
    }

Once again, we can see that the ``storable`` has automatically been wrapped 
in a ``record`` for storage. 

The way this is done is through a ``recordfield``. The same behavior is recovered by 
using 

.. code-block:: python

    from dman import recordfield

    @modelclass(name='model')
    class Model:
        name: str
        content: ManualFile = recordfield()

The ``recordfield`` method has similar arguments to the ``record`` methods
for ``mlist`` and ``mdict``

.. autofunction:: dman.recordfield
    :noindex:

The ``modelclass`` decorator also has all the options that ``dataclass`` 
has. 

.. autofunction:: dman.modelclass
    :noindex:

Setting ``compact=True`` in the above example results in the following serialization

.. code-block:: json

    {
        "_ser__type": "model",
        "_ser__content": {
            "name": "test",
            "content": {
                "target": "1a3c0e93-f20d-438f-a6dc-b23acdde5202",
                "sto_type": "manual"
            }
        }
    }

.. warning::
    
    Usage of ``compact`` is not recommended. Serialization 
    should always work. When deserializing however, if the 
    field did not have the type specified in the ``modelclass``
    definition, the resulting value will be invalid. 

.. note::

    It is possible for an object to be both ``serializable``
    and ``storable``. When a field is specified with a 
    ``storable`` type it will automatically be wrapped in a ``recordfield``.
    This can be avoided.

    .. code-block:: python

        from dman import recordfield, modelclass, field

        @modelclass(name='field', storable=True)
        class Field:
            value: str

        @modelclass(name='model')
        class Model:
            first: Field
            second: Field = field()
        
    When serializing the second field will be serialized, while the first 
    will be stored in a file. 


Saving and Loading Serializables
----------------------------------------

To avoid the hassle with defining a folder structure, ``dman`` provides
some tools that automate the process. These components are 
used in :ref:`common-use`. 

The first basic component is ``save`` which stores a serializable (or storable)
to a file. 

.. autofunction:: dman.save
    :noindex:

As specified, the location of a file 
is determined based on the arguments ``subdir``, ``cluster``, ``generator``, ``key`` and ``base``.
Be sure to use the same arguments when loading from a file with

.. autofunction:: dman.load
    :noindex:

In some cases it will be convenient to both load and save an object 
at the start and the end of a script. For example if you wish to add
experimental results to some ``mdict``. To do so use ``track``:

.. autofunction:: dman.track
    :noindex:

To see these components in practice, refer to :ref:`common-use`. 

.. note::
    It is possible to call the ``save`` and ``load`` functionality 
    of ``track`` manually. This can be useful when you want 
    to save intermediate results. 

    .. code-block:: python

        tracker = track(...)
        with tracker as obj:
            for i in range(nrepeats):
                ... # create some data and add it to obj
                tracker.save(unload=True)

    When the ``unload`` option in ``save`` is set to true, then 
    ``tracker.load`` is called automatically after saving. 
    This causes (non preloaded) storables to be unloaded, which can reduce
    overhead time during the next save (since they will not need to be 
    stored again). 