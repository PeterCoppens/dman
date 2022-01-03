.. _common-use:

Getting Started
========================
We provide an example here of how one could approach. This example will show you

* How to integrate ``numpy`` arrays into the framework.
* How to setup an experiment modelclass.
* How to save and load from cache.

Setting up
------------------------

To setup the example we will need to following imports:

.. code-block:: python

    from dman import modelclass, track, storable
    from dman import recordfield, smdict_factory, smdict

    import numpy as np

The first step is to describe how arrays are stored. We do so by 
creating a ``storable`` type. 

.. code-block:: python

    @storable(name='sarray')
    class sarray(np.ndarray):
        __ext__ = '.npy'
        
        def __write__(self, path):
            with open(path, 'wb') as f:
                np.save(f, self)
            
        @classmethod
        def __read__(cls, path):
            with open(path, 'rb') as f:
                res: np.ndarray = np.load(f) 
                return res.view(cls)

We specify three components. First ``__ext__`` specifies the suffix added
to the created files. The ``__write__`` defines how to store the content 
at a specified path and similarly ``__read__`` defines how to read 
the content from a file. 

We will want to do multiple runs of some test in this example, so first 
lets specify the run type.

.. code-block:: python

    @modelclass(name='run', storable=True)
    class Run:
        input: sarray = recordfield(default=None)
        output: sarray = recordfield(default=None)

        def execute(self, input: np.ndarray, rng: np.random.Generator):
            self.input = self.input.view(sarray)
            transform = rng.standard_normal(size=(100, self.input.shape[0]))
            self.output = transform @ self.input
            self.output = self.output.view(sarray)

Simple enough. A run is a ``modelclass``, which is like a ``dataclass``,
but with some additional features enabling it to be stored automatically. 
We specify that the ``modelclass`` can be stored to a file using ``storable=True``. 

The run contains two fields: ``input`` and ``output``. Note 
that these are specified using a ``recordfield``, 
which has all options from the ``field`` method. We use this method since 
the ``sarray`` fields should be stored. The ``recordfield`` makes this 
clear and enables specifying things like the filename, subdirectory, etc. 
We leave these unspecified in this case and leave filename selection to 
the ``dman`` framework. 

The ``execute`` method simply takes some input, a random generator and 
produces an output using some random transformation matrix. Both 
the input and output are converted to ``sarray`` and stored. 

Next we want to define the experiment configuration and 
how the results are stored. 

.. code-block:: python

    @modelclass(name='experiment')
    class Experiment:
        seed: int = 124
        size: int = 20
        nsample: int = 1000     
        nrepeats: int = 2

        results: smdict = recordfield(
            default_factory=smdict_factory(subdir='results', store_by_key=True), 
            stem='results'
        )

Again, we created a ``modelclass`` here. The first fields are quite standard
and describe the experiment configuration. The ``results`` field however 
is quite involved. It is of type ``smdict``, which stands for storable 
model dictionary. This type is similar to the build-in ``dict`` type. The storable
part means that the dictionary can be stored in a file and the 
model part means that it can contain ``storable`` types of its own. We also specify some 
options. First for the fields ``default_factory`` we specify that the ``smdict_factory``
should store all of its content into a directory ``'results'`` using the ``subdir``
argument. We specify that the keys can be used as file names using ``store_by_key``. 
Finally ``stem`` in the ``recordfield`` then specifies that the file name 
of the stored ``smdict`` should be ``'results'``. 

Running the experiment
----------------------------------
We can run the experiment as follows:

.. code-block:: python

    with track('experiment', default_factory=Experiment) as content:
        experiments: Experiment = content
        if len(experiments.results) > 0:
            print('results already available')
            return

        rng = np.random.default_rng(12345)
        for _ in range(experiments.nrepeats):
            input = rng.random(
                size=(experiments.size, experiments.nsample)
            )
            run = Run(input.view(sarray))
            run.execute(rng)
            experiments.results[f'run-{len(experiments.results)}'] = run

We provide an overview of the above code segment:

1. The ``track`` command 
    is the only non-standard component here. 
    It specifies a file key and a default value that is used when the object can 
    not be loaded from the file key (when it doesn't exist yet). Once the context exists, the file is then saved again.

2. We specify the loaded type.
    The interpreter can not know in advance what the loaded type will be, so we specify 
    it manually. This is good practice since it makes refactoring more convenient. 

3. We check whether some results are already available. 
    a) If so, we can exit the program. 
    b) Otherwise we create some and store them in the ``results`` dictionary. 

.. warning::

    Before running the script execute ``dman init`` in the root folder 
    of your project. Files will be stored in the ``.dman`` folder created there. 


When you then run the script you will see that ``.dman`` is populated as follows:

.. image:: ../assets/common.png
    :width: 320

Note that the ``experiment`` folder is ignored by default. 
The root file is ``experiment.json`` (as specified by the key in ``track``). 
Its content is as follows

.. code-block:: json

    {
        "_ser__type": "experiment",
        "_ser__content": {
            "mode": "random",
            "seed": 124,
            "size": 20,
            "nsample": 1000,
            "nrepeats": 2,
            "results": {
                "_ser__type": "_ser__record",
                "_ser__content": {
                    "target": "results.json",
                    "sto_type": "_sto__smdict"
                }
            }
        }
    }

You can see that all of the basic field types have been stored here. 
They can be adjusted and the result will be loaded next time the 
script is executed. Note that the ``results`` are not 
recorded here however. Instead we have a ``_ser__record`` that 
specifies the location of ``results.json`` relative to the 
file ``experiment.json``. 

Taking a look at the contents of ``results.json`` we can see:

.. code-block:: json

    {
        "store": {
            "run-0": {
                "_ser__type": "_ser__record",
                "_ser__content": {
                    "target": "results/run-0.json",
                    "sto_type": "run"
                }
            },
            "run-1": {
                "_ser__type": "_ser__record",
                "_ser__content": {
                    "target": "results/run-1.json",
                    "sto_type": "run"
                }
            }
        },
        "subdir": "results",
        "store_by_key": true
    }

We can see the options passed to ``smdict_factory`` at the bottom.
Moreover, all of the run keys are there, but their content 
again defers to another file. Specifically ``'results/run-#.json'``.
You can continue like this and see that the ``run-#.json`` files contain 
info about the files containing the ``sarray`` types. These file names 
are specified automatically using ``uuid4`` to guarantee uniqueness.

Specifying Storage Folder
-------------------------------

In the above experiment, the files were stored in
a folder called ``cache/examples:common``. The folder name 
was created based on the script path relative to the folder in which 
``.dman`` is contained. Specifically the script was located in ``examples/common.py``. 

The automatic folder name generation is implemented to avoid potential overlap
between different scripts. Of course, this also means that using 
``track('experiment')`` in two different scripts will save/load from different
files. If you want to use files in different scripts you can do so by specifying 
a ``generator`` as follows

.. code-block:: python

    with track('experiment', default_factory=Experiment, generator='demo') as content:

Doing this, will save/load files from the folder ``.dman/demo`` no matter 
what script the command is executed from. Other options are listed in :ref:`fundamentals`.