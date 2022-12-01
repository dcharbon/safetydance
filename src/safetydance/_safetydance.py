from ast import (
    Assign,
    Attribute,
    Call,
    copy_location,
    fix_missing_locations,
    Index,
    Load,
    Module,
    Name,
    NodeTransformer,
    parse,
    Store,
    Subscript,
)
from dataclasses import dataclass
from importlib import import_module
from inspect import currentframe, getclosurevars, getmodule, stack
from types import ModuleType
from typing import Any, Callable, Dict, Type, TypeVar, Generic
from .extensions import enter_step, exit_step, STEPBODY_EXTENSION_REGISTRY
from .file_util import code_to_ast
from .jupyter import is_jupyter
import functools
import inspect


def step_decorator(f):
    f.is_step_decorator = True
    return f


T = TypeVar("T")


@dataclass(frozen=True)
class ContextKey(Generic[T]):
    datatype: T
    description: str
    initializer: Callable[["Context"], T]


def step_data(
    key_type: Type,
    description: str = None,
    initializer: Callable[["Context"], Type] = None,
):
    return ContextKey(key_type, description, initializer)


class Context(Dict[ContextKey, Any]):
    def __getitem__(self, key: ContextKey):
        """
        A ``Context`` differs from a plain ``Dict`` in that it will initialize a key
        with a default value if the key defines a default value initializer.
        """
        if key not in self and key.initializer is not None:
            initial_value = key.initializer(self)
            self[key] = initial_value
        return super().__getitem__(key)


class NestingContext(Context):
    def __init__(self, *args, parent: Context = None, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.parent = parent

    def __missing__(self, key):
        if self.parent is not None:
            return self.parent[key]
        raise KeyError(key)


def get_context():
    calling_frame = currentframe().f_back
    parent_frame = calling_frame.f_back
    context = parent_frame.f_locals.get('context', None)
    return context


class Step:
    def __init__(self, f: Callable, step_rewriter):
        self.f_original = f
        self.f = None
        self.step_rewriter = step_rewriter

    def __call__(self, *args, **kwargs):
        __tracebackhide__ = True
        if self.f is None:
            self.rewrite()
        context = get_context()
        enter_step(context, self)
        ret = self.f(*args, **kwargs)
        exit_step(context, self)
        return ret

    def rewrite(self):
        if hasattr(self.f_original, "__rewritten_step__") and not is_jupyter():
            self.f = self.f_original.__rewritten_step__
            return
        in_tree = code_to_ast(self.f_original)
        filename, lineno = code_to_ast.get_file_info(self.f_original)
        out_tree = self.step_rewriter(self.f_original).visit(in_tree)
        new_func_name = self.f_original.__name__
        func_scope = self.f_original.__globals__
        for key, value in (
            ("Context", Context),
            ("safetydance", __import__(__name__)),
        ):
            if key not in self.f_original.__globals__:
                self.f_original.__globals__[key] = value
        # Compile the new function in the old function's scope. If we don't change the
        # name, this actually overrides the old function with the new one
        if not isinstance(out_tree, Module):
            # As of python 3.8.0 the signature for Module has changed, this fix should
            # work for < 3.8 as well as 3.8
            # print(f'dumping module { dump_tree(out_tree) } ')
            # out_tree = Module(body=[out_tree])
            module = parse("")
            module.body = [out_tree]
            out_tree = module
        exec(compile(out_tree, f"{filename}", "exec"), func_scope)
        self.f = func_scope[new_func_name]
        self.f.IsStep = True
        setattr(self.f_original, "__rewritten_step__", self.f)
        # make sure that the function hasn't been overwritten due to the reparsing of
        # the source file. This is necessary to support extensions.
        m = import_module(self.__module__)
        setattr(m, self.__name__, self)


class StepRewriter(NodeTransformer):
    def __init__(self, f: Callable):
        super().__init__()
        self.f = f
        self.step_body_rewriter = StepBodyRewriter(f)
        self.modulevars = vars(getmodule(f))

    def is_step_decorator(self, decorator):
        if not hasattr(decorator, "id"):
            return False
        decorator = self.f.__globals__.get(decorator.id)
        return hasattr(decorator, "is_step_decorator")

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.decorator_list = [
            decorator
            for decorator in node.decorator_list
            if not self.is_step_decorator(decorator)
        ]
        newbody = [
            # context = safetydance.get_context()
            Assign(
                targets=[
                    Name(id='context', ctx=Store()),
                ],
                value=Call(
                    func=Attribute(value=Name(id='safetydance', ctx=Load()), attr='get_context', ctx=Load()),
                    args=[],
                    keywords=[],
                ),
                type_comment=None,
            ),
        ]
        for n in node.body:
            n = self.step_body_rewriter.visit(n)
            try:
                newbody.extend(iter(n))
            except TypeError:
                newbody.append(n)
        node.body = newbody
        return fix_missing_locations(node)


@step_decorator
def step(f, step_rewriter=StepRewriter, step_class=Step):
    """
    Rewrite the step function so:
    1. `context: Context` is the first parameter
    2. All references to ContextKey instances are rewritten as
       `context[key]`
    """
    return functools.wraps(f)(step_class(f, step_rewriter=step_rewriter))


class Script(Step):
    def __call__(self, *args, **kwargs):
        __tracebackhide__ = True
        if self.f is None:
            self.rewrite()
        parent_context = get_context()
        context = NestingContext(parent=parent_context) 
        enter_step(context, self)
        ret = self.f(*args, **kwargs)
        exit_step(context, self)
        return ret


class StepBodyRewriter(NodeTransformer):
    def __init__(self, f: Callable):
        super().__init__()
        self.f = f
        self.closurevars = getclosurevars(f)
        self.modulevars = vars(getmodule(f))
        self.step_globals = f.__globals__

    def resolve(self, id: str):
        if id in self.closurevars.nonlocals:
            return self.closurevars.nonlocals.get(id)
        if id in self.closurevars.globals:
            return self.closurevars.globals.get(id)
        if id in self.closurevars.unbound:
            return None

    def visit(self, node):
        node = super().visit(node)
        for transformer in STEPBODY_EXTENSION_REGISTRY:
            node = transformer.visit(node)
        return node

    def visit_Name(self, node):
        """
        If the name resolves to a ContextKey, rewrite it as a subscript
        of the `context`.
        """
        sig = inspect.signature(self.f)
        resolved = self.step_globals.get(node.id, None)

        if resolved is not None and isinstance(resolved, ContextKey):
            if node.id in sig.parameters:
                return node
            else:
                return fix_missing_locations(
                    copy_location(
                        Subscript(
                            value=Name(id="context", ctx=Load()),
                            slice=Index(value=Name(id=node.id, ctx=Load())),
                            ctx=node.ctx,
                        ),
                        node,
                    )
                )
        else:
            return node

    def rewrite_as_context_lookup(self, node):
        ctx = node.ctx
        node.ctx = Load()
        return fix_missing_locations(
            copy_location(
                Subscript(
                    value=Name(id="context", ctx=Load()),
                    slice=Index(value=node),
                    ctx=ctx,
                ),
                node,
            )
        )

    def visit_Attribute(self, node):
        if isinstance(node.value, Attribute):
            node, resolved = self.recurse_Attribute(node)
            return node
        node.value = self.visit(node.value)
        return node

    def resolve_Attribute_attr(self, node, resolved):
        attr_value = getattr(resolved, node.attr)
        if isinstance(attr_value, ContextKey):
            node = self.rewrite_as_context_lookup(node)
            return (node, None)
        elif isinstance(attr_value, ModuleType) or isinstance(attr_value, type):
            return (node, attr_value)
        return (node, None)

    def recurse_Attribute(self, node):
        if isinstance(node.value, Name):
            resolved = self.step_globals.get(node.value.id, None)
            if resolved is not None:
                if isinstance(resolved, ContextKey):
                    node.value = self.visit_Name(node.value)
                    return (node, None)
                elif isinstance(resolved, ModuleType) or isinstance(resolved, type):
                    return self.resolve_Attribute_attr(node, resolved)
        elif isinstance(node.value, Attribute):
            result_value_node, resolved_value = self.recurse_Attribute(node.value)
            if resolved_value is not None:
                return self.resolve_Attribute_attr(node, resolved_value)
            else:
                node.value = result_value_node
                return (node, None)
        return (node, None)


@step_decorator
def script(f, script_rewriter=StepRewriter, script_class=Script):
    """
    Rewrite the function as a Script
    remember Signature.replace
    """
    return functools.wraps(f)(script_class(f, step_rewriter=script_rewriter))
