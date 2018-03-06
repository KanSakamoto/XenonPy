# Copyright 2017 TsumiNa. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.


import sys, traceback
import warnings
import pandas as pd
import numpy as np
from six import string_types
from multiprocessing import Pool, cpu_count
from sklearn.base import TransformerMixin, BaseEstimator


class BaseFeature(BaseEstimator, TransformerMixin):
    """
    Abstract class to calculate features from raw materials input data
    such a compound formula or a pymatgen crystal structure or
    bandstructure object.
    ## Using a BaseFeaturizer Class
    There are multiple ways for running the featurize routines:
        `featurize`: Featurize a single entry
        `featurize_many`: Featurize a list of entries
        `featurize_dataframe`: Compute features for many entries, store results
            as columns in a dataframe
    Some featurizers require first calling the `fit` method before the
    featurization methods can function. Generally, you pass the dataset to
    fit to determine which features a featurizer should compute. For example,
    a featurizer that returns the partial radial distribution function
    may need to know which elements are present in a dataset.
    You can also employ the featurizer as part of a ScikitLearn Pipeline object.
    For these cases, scikit-learn calls the `transform` function of the
    `BaseFeaturizer` which is a less-featured wrapper of `featurize_many`. You
    would then provide your input data as an array to the Pipeline, which would
    output the featurers as an array.
    Beyond the featurizing capability, BaseFeaturizer also includes methods
    for retrieving proper references for a featurizer. The `citations` function
    returns a list of papers that should be cited. The `implementors` function
    returns a list of people who wrote the featurizer, so that you know
    who to contact with questions.
    ## Implementing a New BaseFeaturizer Class
    These operations must be implemented for each new featurizer:
        `featurize` - Takes a single material as input, returns the features of
            that material.
        `feature_labels` - Generates a human-meaningful name for each of the
            features.
        `citations` - Returns a list of citations in BibTeX format
        `implementors` - Returns a list of people who contributed writing a paper
    None of these operations should change the state of the featurizer. I.e.,
    running each method twice should no produce different results, no class
    attributes should be changed, unning one operation should not affect the
    output of another.
    All options of the featurizer must be set by the `__init__` function. All
    options must be listed as keyword arguments with default values, and the
    value must be saved as a class attribute with the same name (e.g., argument
    `n` should be stored in `self.n`). These requirements are necessary for
    compatibility with the `get_params` and `set_params` methods of
    `BaseEstimator`, which enable easy interoperability with scikit-learn.
    Depending on the complexity of your featurizer, it may be worthwhile to
    implement a `from_preset` class method. The `from_preset` method takes the
    name of a preset and returns an instance of the featurizer with some
    hard-coded set of inputs. The `from_preset` option is particularly useful
    for defining the settings used by papers in the literature.
    Optionally, you can implement the `fit` operation if there are attributes of
    your featurizer that must be set for the featurizer to work. Any variables
    that are set by fitting should be stored as class attributes that end with
    an underscore. (This follows the pattern used by scikit-learn).
    Another implementation to consider is whether it is worth making any utility
    operations for your featurizer. `featurize` must return a list of features,
    but this may not be the most natural representation for your features (e.g.,
    a `dict` could be better). Making a separate function for computing features
    in this natural representation and having the `featurize` function call this
    method and then convert the data into a list is a recommended approach.
    Users who want to compute the representation in the natural form can use the
    utility function and users who want the data in a ML-ready format (list) can
    call `featurize`. See `PartialRadialDistributionFunction` for an example of
    this concept.
    ## Documenting a BaseFeaturizer
    The class documentation for each featurizer must contain a description of
    the options and the features that will be computed. The options of the class
     must all be defined in the `__init__` function of the class, and we
     recommend documenting them using the
    [Google style](https://google.github.io/styleguide/pyguide.html).
    We recommend starting the class documentation with a high-level overview of
    the features. For example, mention what kind of characteristics of the
    material they describe and refer the reader to a paper that describes these
    features well (use a hyperlink if possible, so that the readthedocs will
    like to that paper). Then, describe each of the individual features in a
    block named "Features". It is necessary here to give the user enough
    information for user to map a feature name what it means. The objective in
    this part is to allow people to understand what each column of their
    dataframe is without having to read the Python code. You do not need to
    explain all of the math/algorithms behind each feature for them to be able
    to reproduce the feature, just to get an idea what it is.
    """

    def set_n_jobs(self, n_jobs):
        """Set the number of threads for this """
        self._n_jobs = n_jobs

    @property
    def n_jobs(self):
        return self._n_jobs if hasattr(self, '_n_jobs') else cpu_count()

    def fit(self, X, y=None, **fit_kwargs):
        """Update the parameters of this featurizer based on available data
        Args:
            X - [list of tuples], training data
        Returns:
            self
            """
        return self

    def transform(self, X):
        """Compute features for a list of inputs"""

        return self.featurize_many(X, ignore_errors=True)

    def featurize_dataframe(self, df, col_id, ignore_errors=False,
                            return_errors=False, inplace=True):
        """
        Compute features for all entries contained in input dataframe.
        Args:
            df (Pandas dataframe): Dataframe containing input data.
            col_id (str or list of str): column label containing objects to
                featurize. Can be multiple labels if the featurize function
                requires multiple inputs.
            ignore_errors (bool): Returns NaN for dataframe rows where
                exceptions are thrown if True. If False, exceptions
                are thrown as normal.
            return_errors (bool). Returns the errors encountered for each
                row in a separate `XFeaturizer errors` column if True. Requires
                ignore_errors to be True.
            inplace (bool): Whether to add new columns to input dataframe (df)
        Returns:
            updated dataframe.
        """

        # If only one column and user provided a string, put it inside a list
        if isinstance(col_id, string_types):
            col_id = [col_id]

        # Generate the feature labels
        labels = self.feature_labels()

        # Check names to avoid overwriting the current columns
        for col in df.columns.values:
            if col in labels:
                raise ValueError('"{}" exists in input dataframe'.format(col))

        # Compute the features
        features = self.featurize_many(df[col_id].values,
                                       ignore_errors=ignore_errors,
                                       return_errors=return_errors)
        if return_errors:
            labels.append(self.__class__.__name__ + " Exceptions")

        # Create dataframe with the new features
        res = pd.DataFrame(features, index=df.index, columns=labels)

        # Update the existing dataframe
        if inplace:
            for k in labels:
                df[k] = res[k]
            return df
        else:
            return pd.concat([df, res], axis=1)

    def featurize_many(self, entries, ignore_errors=False, return_errors=False):
        """
        Featurize a list of entries.
        If `featurize` takes multiple inputs, supply inputs as a list of tuples.
        Args:
            entries (list): A list of entries to be featurized.
            ignore_errors (bool): Returns NaN for entries where exceptions are
                thrown if True. If False, exceptions are thrown as normal.
            return_errors (bool): If True, returns the feature list as
                determined by ignore_errors with traceback strings added
                as an extra 'feature'. Entries which featurize without
                exceptions have this extra feature set to NaN.
        Returns:
            (list) features for each entry.
        """

        if return_errors and not ignore_errors:
            raise ValueError("Please set ignore_errors to True to use"
                             " return_errors.")

        self.__ignore_errors = ignore_errors
        self.__return_errors = return_errors

        # Check inputs
        if not hasattr(entries, '__getitem__'):
            raise Exception("'entries' must be a list-like object")

        # Special case: Empty list
        if len(entries) is 0:
            return []

        # If the featurize function only has a single arg, zip the inputs
        if not isinstance(entries[0], (tuple, list, np.ndarray)):
            entries = zip(entries)

        # Run the actual featurization
        if self.n_jobs == 1:
            return [self.featurize_wrapper(x) for x in entries]
        else:
            if sys.version_info[0] < 3:
                warnings.warn("Multiprocessing is not supported in "
                              "matminer for Python 2.x. Multiprocessing has "
                              "been disabled. Please upgrade to Python 3.x to "
                              "enable multiprocessing.")
                self.set_n_jobs(1)
                return self.featurize_many(entries,
                                           ignore_errors=ignore_errors,
                                           return_errors=return_errors)
            with Pool(self.n_jobs) as p:
                return p.map(self.featurize_wrapper, entries)

    def featurize_wrapper(self, x):
        """
        An exception wrapper for featurize, used in featurize_many and
        featurize_dataframe. featurize_wrapper changes the behavior of featurize
        when ignore_errors is True in featurize_many/dataframe.
        Args:
             x: input data to featurize (type depends on featurizer).
        Returns:
            (list) one or more features.
        """
        try:
            # Successful featurization returns nan for an error.
            if self.__return_errors:
                return self.featurize(*x) + [float("nan")]
            else:
                return self.featurize(*x)
        except BaseException:
            if self.__ignore_errors:
                if self.__return_errors:
                    features = [float("nan")] * len(self.feature_labels())
                    error = traceback.format_exception(*sys.exc_info())
                    return features + ["".join(error)]
                else:
                    return [float("nan")] * len(self.feature_labels())
            else:
                raise

    def featurize(self, *x):
        """
        Main featurizer function, which has to be implemented
        in any derived featurizer subclass.
        Args:
            x: input data to featurize (type depends on featurizer).
        Returns:
            (list) one or more features.
        """

        raise NotImplementedError("featurize() is not defined!")

    def feature_labels(self):
        """
        Generate attribute names.
        Returns:
            ([str]) attribute labels.
        """

        raise NotImplementedError("feature_labels() is not defined!")

    def citations(self):
        """
        Citation(s) and reference(s) for this feature.
        Returns:
            (list) each element should be a string citation,
                ideally in BibTeX format.
        """

        raise NotImplementedError("citations() is not defined!")

    def implementors(self):
        """
        List of implementors of the feature.
        Returns:
            (list) each element should either be a string with author name (e.g.,
                "Anubhav Jain") or a dictionary  with required key "name" and other
                keys like "email" or "institution" (e.g., {"name": "Anubhav
                Jain", "email": "ajain@lbl.gov", "institution": "LBNL"}).
        """

        raise NotImplementedError("implementors() is not defined!")
