from os.path import dirname
from os.path import join
from xdoctest import utils


def build_demo_extmod():
    """
    CommandLine:
        python testing/test_binary_ext.py build_demo_extmod
    """
    import os
    import glob
    import sys
    testing_dpath = dirname(__file__)

    verstr, details = sys.version.split(' ', 1)
    # poor man's hash (in case python wasnt built with hashlib)
    coded = (int(details.encode('utf8').hex(), 16) % (2 ** 32))
    hashid = coded.to_bytes(4, 'big').hex()

    src_dpath = join(testing_dpath, 'pybind11_test')
    bin_dpath = join(src_dpath, 'tmp', 'install_{}.{}'.format(verstr, hashid))
    print('src_dpath = {!r}'.format(src_dpath))
    print('bin_dpath = {!r}'.format(bin_dpath))
    utils.ensuredir(bin_dpath)
    candidates = list(glob.glob(join(bin_dpath, 'my_ext.*')))
    if len(candidates) == 0:
        pip_args = ['install', '--target={}'.format(bin_dpath), src_dpath]
        print('pip_args = {!r}'.format(pip_args))
        if 0:
            pyexe = sys.executable
            ret = os.system(pyexe + ' -m pip ' + ' '.join(pip_args))
        else:
            from pip._internal import main as pip_main
            if callable(pip_main):
                ret = pip_main(pip_args)
            else:
                ret = pip_main.main(pip_args)
        assert ret == 0, 'unable to build our pybind11 example'
        candidates = list(glob.glob(join(bin_dpath, 'my_ext.*')))
    assert len(candidates) == 1
    extmod_fpath = candidates[0]
    return extmod_fpath


def test_run_binary_doctests():
    """
    Tests that we can run doctests in a compiled pybind11 module

    CommandLine:
        python ~/code/xdoctest/testing/test_binary_ext.py test_run_binary_doctests
    """
    extmod_fpath = build_demo_extmod()
    print('extmod_fpath = {!r}'.format(extmod_fpath))
    from xdoctest import runner
    # results = runner.doctest_module(extmod_fpath, analysis='auto')
    results = runner.doctest_module(extmod_fpath, analysis='dynamic',
                                    command='list', argv=[], verbose=3)
    print('results = {!r}'.format(results))

    results = runner.doctest_module(extmod_fpath, analysis='dynamic',
                                    command='all', argv=[], verbose=3)
    print('results = {!r}'.format(results))
    assert results['n_passed'] == 1


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/xdoctest/testing/test_binary_ext.py
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
