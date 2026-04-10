import warnings
import traceback

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        import cupy as cp
        import cupyx.scipy.sparse as cp_sparse
    
    _test = cp.array([1.0, 2.0])
    del _test
    print(f"CuPy OK! CUDA runtime: {cp.cuda.runtime.runtimeGetVersion()}")
    print(f"Device count: {cp.cuda.runtime.getDeviceCount()}")
except Exception as e:
    print(f"CuPy failed: {e}")
    traceback.print_exc()
