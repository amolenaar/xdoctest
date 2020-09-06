"""
Utilities for handling Jupyter / IPython notebooks

This code is copied and modified from nbimporter
(https://github.com/grst/nbimporter/blob/master/nbimporter.py) which is not
actively maintained (otherwise we would use it as a dependency).

Note that using this behavior is very much discouraged, it would be far better
if you maintained your reusable code in separate python modules.  See
https://github.com/grst/nbimporter for reasons.

----

Allow for importing of IPython Notebooks as modules from Jupyter v4.

Updated from module collated here:
https://github.com/adrn/ipython/blob/master/examples/Notebook/Importing%20Notebooks.ipynb

Importing from a notebook is different from a module: because one
typically keeps many computations and tests besides exportable defs,
here we only run code which either defines a function or a class, or
imports code from other modules and notebooks. This behaviour can be
disabled by setting nbimporter.options['only_defs'] = False.

Furthermore, in order to provide per-notebook initialisation, if a
special function __nbinit__() is defined in the notebook, it will be
executed the first time an import statement is. This behaviour can be
disabled by setting nbimporter.options['run_nbinit'] = False.

Finally, you can set the encoding of the notebooks with
nbimporter.options['encoding']. The default is 'utf-8'.
"""

import io
import os
import sys
import types
import ast
import nbformat
from os.path import basename, dirname
from IPython import get_ipython
from IPython.core.interactiveshell import InteractiveShell


def _find_notebook(fullname, path=None):
    """ Find a notebook, given its fully qualified name and an optional path

    This turns "foo.bar" into "foo/bar.ipynb"
    and tries turning "Foo_Bar" into "Foo Bar" if Foo_Bar
    does not exist.
    """
    name = fullname.rsplit('.', 1)[-1]
    if not path:
        path = ['']
    for d in path:
        nb_path = os.path.join(d, name + ".ipynb")
        if os.path.isfile(nb_path):
            return nb_path
        # let import Notebook_Name find "Notebook Name.ipynb"
        nb_path = nb_path.replace("_", " ")
        if os.path.isfile(nb_path):
            return nb_path


class CellDeleter(ast.NodeTransformer):
    """ Removes all nodes from an AST which are not suitable
    for exporting out of a notebook. """
    def visit(self, node):
        """ Visit a node. """
        if node.__class__.__name__ in ['Module', 'FunctionDef', 'ClassDef',
                                       'Import', 'ImportFrom']:
            return node
        return None


class NotebookLoader(object):
    """ Module Loader for Jupyter Notebooks. """

    default_options = {
        'only_defs': False,
        'run_nbinit': True,
        'encoding': 'utf-8'
    }

    def __init__(self, path=None):
        self.shell = InteractiveShell.instance()
        self.path = path
        self.options = self.default_options.copy()

    def load_module(self, fullname=None, fpath=None):
        """import a notebook as a module"""
        if fpath is None:
            fpath = _find_notebook(fullname, self.path)

        # load the notebook object
        nb_version = nbformat.current_nbformat

        with io.open(fpath, 'r', encoding=self.options['encoding']) as f:
            nb = nbformat.read(f, nb_version)

        # create the module and add it to sys.modules
        # if name in sys.modules:
        #    return sys.modules[name]
        mod = types.ModuleType(fullname)
        mod.__file__ = fpath
        mod.__loader__ = self
        mod.__dict__['get_ipython'] = get_ipython

        # Only do something if it's a python notebook
        if nb.metadata.kernelspec.language != 'python':
            print("Ignoring '%s': not a python notebook." % fpath)
            return mod

        # print("Importing Jupyter notebook from %s" % fpath)
        sys.modules[fullname] = mod

        # extra work to ensure that magics that would affect the user_ns
        # actually affect the notebook module's ns
        save_user_ns = self.shell.user_ns
        self.shell.user_ns = mod.__dict__

        try:
            deleter = CellDeleter()
            for cell in filter(lambda c: c.cell_type == 'code', nb.cells):
                # transform the input into executable Python
                code = self.shell.input_transformer_manager.transform_cell(cell.source)
                if self.options['only_defs']:
                    # Remove anything that isn't a def or a class
                    tree = deleter.generic_visit(ast.parse(code))
                else:
                    tree = ast.parse(code)
                # run the code in the module
                codeobj = compile(tree, filename=fpath, mode='exec')
                exec(codeobj, mod.__dict__)
        finally:
            self.shell.user_ns = save_user_ns

        # Run any initialisation if available, but only once
        if self.options['run_nbinit'] and '__nbinit_done__' not in mod.__dict__:
            try:
                mod.__nbinit__()
                mod.__nbinit_done__ = True
            except (KeyError, AttributeError):
                pass

        return mod


def import_notebook_from_path(ipynb_fpath, only_defs=False):
    """
    Import an IPython notebook as a module from a full path and try to maintain
    clean sys.path variables.

    Args:
        ipynb_fpath (str | Path): path to the ipython notebook file to import
        only_defs (bool, default=False): if True ignores all non-definition
            statements

    Example:
        >>> # xdoctest: +REQUIRES(module:IPython, module:nbconvert)
        >>> from xdoctest import utils
        >>> from os.path import join
        >>> self = utils.TempDir()
        >>> dpath = self.ensure()
        >>> ipynb_fpath = join(dpath, 'test_import_notebook.ipydb')
        >>> cells = [
        >>>     utils.codeblock(
        >>>         '''
        >>>         def foo():
        >>>             return 'bar'
        >>>         '''),
        >>>     utils.codeblock(
        >>>         '''
        >>>         x = 1
        >>>         ''')
        >>> ]
        >>> _make_test_notebook_fpath(ipynb_fpath, cells)
        >>> module = import_notebook_from_path(ipynb_fpath)
        >>> assert module.foo() == 'bar'
        >>> assert module.x == 1
    """
    ipynb_fname = basename(ipynb_fpath)
    fname_noext = ipynb_fname.rsplit('.', 1)[0]
    ipynb_modname = fname_noext.replace(' ', '_')

    # hack around the importlib machinery
    loader = NotebookLoader()
    loader.options['only_defs'] = only_defs
    module = loader.load_module(ipynb_modname, ipynb_fpath)
    return module


def execute_notebook(ipynb_fpath, timeout=None):
    """
    Execute an IPython notebook in a separate kernel

    Args:
        ipynb_fpath (str | Path): path to the ipython notebook file to import

    Returns:
        nb : NotebookNode
            The executed notebook.
        resources : dictionary
            Additional resources used in the conversion process.

    Example:
        >>> # xdoctest: +REQUIRES(module:IPython, module:nbconvert)
        >>> from xdoctest import utils
        >>> from os.path import join
        >>> self = utils.TempDir()
        >>> dpath = self.ensure()
        >>> ipynb_fpath = join(dpath, 'hello_world.ipydb')
        >>> _make_test_notebook_fpath(ipynb_fpath, [utils.codeblock(
        >>>     '''
        >>>     print('hello world')
        >>>     ''')])
        >>> nb, resources = execute_notebook(ipynb_fpath)
        >>> for cell in nb['cells']:
        >>>     assert len(cell['outputs']) == 1
    """
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor
    dpath = dirname(ipynb_fpath)
    ep = ExecutePreprocessor(timeout=timeout)
    # kernel_name='python3')
    with open(ipynb_fpath) as file:
        nb = nbformat.read(file, as_version=nbformat.NO_CONVERT)
    nb, resources = ep.preprocess(nb, {'metadata': {'path': dpath}})
    return nb, resources


def _make_test_notebook_fpath(fpath, cell_sources):
    """
    Helper for testing
    """
    import json
    data = {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
                },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython", "version": 3
                    },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.8.3"
                }
            },
        "nbformat": 4,
        "nbformat_minor": 4
        }

    for source in cell_sources:
        data['cells'].append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                source
                ]
            })

    with open(fpath, 'w') as file:
        json.dump(data, file)
    return fpath
