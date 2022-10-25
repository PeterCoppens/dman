"""
Panda DataFrames
============================

We apply ``dman`` to handle a ``DataFrame`` from ``panda``.
"""

# %%
# To do so we will need the following imports

import datetime, textwrap, os, urllib.request, tempfile
import pandas as pd

import dman
from dman import tui


# %%
# We then load the iris dataset.
KEY = "iris"
URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data"
HEADER = ["sepal.length", "sepal.width", "petal.length", "petal.width", "variety"]

with tempfile.TemporaryDirectory() as base:
    path = os.path.join(base, f"{KEY}.data")
    urllib.request.urlretrieve(URL, path)

    df = pd.read_csv(
        path,
        sep=",",
        header=None,
        names=HEADER,
    )

    df["variety"] = df["variety"].apply(lambda x: x.split("-")[-1])


# %%
# To turn the ``DataFrame`` into a storable we register it as one manually.

dman.register_storable(
    "pd_dataframe",
    pd.DataFrame,
    write=lambda df, path: df.to_csv(path),
    read=lambda path: pd.read_csv(path),
)
pd.DataFrame.__ext__ = '.csv'

# %%
# We can now save a ``DataFrame`` directly using a ``record``.
dman.save('iris', dman.record(df, stem='iris'))
df = dman.load('iris').content
print(df)
tui.walk_directory(dman.get_directory('iris'), show_content=['.json'])

# %%
# Alternatively we can define a more complex storage architecture.

@dman.modelclass(storable=True)
class DataItem:
    data: pd.DataFrame = dman.recordfield(stem='data')
    description: str = ''
    created: str = dman.field(default_factory=lambda: datetime.datetime.now().isoformat())


item = DataItem(df, 
    textwrap.dedent('''
    This is perhaps the best known database to be found in the pattern recognition literature. 
    Fisher's paper is a classic in the field and is referenced frequently to this day. 
    (See Duda & Hart, for example.) The data set contains 3 classes of 50 instances each, 
    where each class refers to a type of iris plant. One class is linearly separable
    from the other 2; the latter are NOT linearly separable from each other.

    Predicted attribute: class of iris plant.

    This is an exceedingly simple domain.

    This data differs from the data presented in Fishers article (identified by 
    Steve Chadwick, spchadwick '@' espeedaz.net ). The 35th sample should be: 
    4.9,3.1,1.5,0.2,"Iris-setosa" where the error is in the fourth feature. 
    The 38th sample: 4.9,3.6,1.4,0.1,"Iris-setosa" where the errors are in the 
    second and third features.

    Source: https://archive.ics.uci.edu/ml/datasets/iris
    ''')
)

container = dman.mdict(store_by_key=True, store_subdir=True)
container['iris'] = item
dman.save('dataframes', container)
item: DataItem = dman.load('dataframes')['iris']
print(item.data)
tui.walk_directory(dman.get_directory('dataframes'), show_content=['.json'])
