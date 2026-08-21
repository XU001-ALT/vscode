"""Python 版本兼容补丁。

仅在「3.14 RC 系列」上生效：RC 的 typing._eval_type 参数名为 parent_fwdref，
而 pydantic>=2.12 面向 3.14 正式版传的是 prefer_fwd_module。
正式版 / 其他版本 Python 不做任何修改。
必须在导入 fastapi / pydantic 模型之前 import 本模块。
"""
import inspect
import typing

if not getattr(typing._eval_type, "_cd_compat_patched", False):
    _params = list(inspect.signature(typing._eval_type).parameters)

    if "prefer_fwd_module" not in _params and "parent_fwdref" in _params:
        _orig_eval_type = typing._eval_type

        def _compat_eval_type(*args, **kwargs):
            if "prefer_fwd_module" in kwargs:
                kwargs["parent_fwdref"] = kwargs.pop("prefer_fwd_module")
            return _orig_eval_type(*args, **kwargs)

        _compat_eval_type._cd_compat_patched = True
        typing._eval_type = _compat_eval_type
