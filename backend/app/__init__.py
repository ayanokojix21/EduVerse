import sys
import types
import importlib

# ─── LangChain Shimming Layer ──────────────────────────────────────

def _shim_module(source: str, target: str):
    """Injects a shim into sys.modules so that 'import source' returns 'target'."""
    if source in sys.modules:
        return
    try:
        sys.modules[source] = importlib.import_module(target)
    except (ImportError, Exception):
        pass

# 1. Base Redirects
_shim_module("langchain.retrievers", "langchain_classic.retrievers")
_shim_module("langchain.indexes", "langchain_community.indexes")
_shim_module("langchain.vectorstores", "langchain_community.vectorstores")
_shim_module("langchain.chains", "langchain_community.chains")

# 2. Forge missing legacy components
try:
    if "langchain.chains.query_constructor" not in sys.modules:
        m = types.ModuleType("langchain.chains.query_constructor")
        sys.modules["langchain.chains.query_constructor"] = m
    
    if "langchain.chains.query_constructor.schema" not in sys.modules:
        s = types.ModuleType("langchain.chains.query_constructor.schema")
        class AttributeInfo:
            def __init__(self, *args, **kwargs): pass
        s.AttributeInfo = AttributeInfo
        sys.modules["langchain.chains.query_constructor.schema"] = s
except Exception:
    pass
