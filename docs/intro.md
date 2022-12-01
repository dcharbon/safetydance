---
jupytext:
  cell_metadata_filter: -all
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# SafetyDance

SafetyDance is a library enabling the development of tiny imperative languages
embedded in Python. SafetyDance was inspired by
[Cucumber](https://cucumber.io/).

The principle use of SafetyDance is in defining a set of functions that are meant
to be used together as composable steps. For example:

```{note} Not a working example!
Just an illustration of the concept.
```

```python
from kitchen import *

@script
def make_peanut_butter_and_jelly()
    retrieve_from_pantry("peanut butter")
    retrieve_from_pantry("jelly")
    retrieve_from_pantry("bread")
    # let's assume retrieve() returns an object with steps like "from()"
    slice1 = retrieve("slice").from("bread")
    slice2 = retrieve("slice").from("bread")
    # let's assume spread() returns an object with steps like "onto()"
    spread("jelly").onto(slice1)
    spread("peanut butter").onto(slice2)
    # let's assume the library knows to place the slices together correctly
    # with the peanut butter and jelly on the inside of the sandwich
    place(slice1).onto(slice2)
```

Here's another contrived example of using a SafetyDance library:


```{note} Not a working example!
Just an illustration of the concept.
```

```python
from safetydance.bot import *

@script
def do_cha_cha_slide(count):
    # first, let's gather our dancers
    dancers_to_the_floor(count)
    # now, we'll tell those dancers what to do!
    To_the_left()
    Take_it_back_now_yall()
    One_hop_this_time()
    # prep the dancers to use their right foot, then stomp
    Right_foot(); lets_stomp()
    # prep the dancers to use their left foot, then stomp
    Left_foot(); lets_stomp()
    Cha_cha_real_smooth()
```

## Design Goals

- Enable the development of tiny imperative languages similar to the testing languages that
  can be built using [Cucumber](https://cucumber.io).
- Let folks code in Python directly (antigoal: don't worry about regular expressions and an external syntax)
- Enable type checking on uses and assignments to variables in the shared context.
- Enable temporal checking on variables in the shared context; that is, enable validating that a given step
  will find the variables it needs from the context because a prior step will have defined that variable to the
  context.
- Enable the automatic parallelization of the execution of steps based on the dependencies of the step.
- To enable the develpment of [safetydance_test](https://gitlab.com/openteams/safetydance_test) for BDD testing.

## A Crude Working Example

```{admonition} This isn't a great example, really...
:class: tip
A better example is under development, hopefully.
```

```{code-cell}
from dataclasses import dataclass
from safetydance import Context, ContextKey, script, step, step_data
import logging

logging.basicConfig(level=logging.DEBUG)

@dataclass
class Foo:
    bar: int


# `step_data` are context variables shared between the steps
One = step_data(int)
Two = step_data(int, "Here's a description for ya!")
Logger = step_data(logging.Logger)
SomeFoo = step_data(Foo)

@step
def step_one():
    # The variable `context` is implicitly defined by `@step`
    # Assignments and references to `step_data` are resolved through the `context`
    # by rewriting performed by the `@step` decorator
    One = 1            # context[One] = 1
    SomeFoo = Foo(42)  # context[SomeFoo] = 42
    Logger = logging.getLogger("FooLog")  # context[Logger] = ...


@step
def step_two():
    Two = 2  # context[Two] = 2


@step
def step_with_args(arg1, arg2=None):
    print(f"arg1: {arg1},  arg2: {arg2}")
    print(f"One: {One}, Two: {Two}")  # print(f"One: {context[One]}, Two: {context[Two]})
    step_one()


# `@script` functions define a `context` while `@step` functions assume one
# exists and can be retrieved. A `context` functions as a shared lexical scope.
@script
def my_script():
    # A `context` is implicitly created by the `@script` decorator
    # context = NestingContext()
    step_one()
    step_two()
    step_with_args("no keyword arg provided")
    step_with_args("keyword arg provided", arg2="this is the keyword arg")
    # `@script` functions are also steps!
    One = 3               # context[One] = 3
    step_with_args("One should be 3, now")
    print(f"SomeFoo.bar: {SomeFoo.bar}")  # print(f"SomeFoo.bar: {context[SomeFoo.bar]}")
    Logger.info(f"SomeFoo.bar: {SomeFoo.bar}")  # context[Logger].info(...)

my_script()
```

```{tableofcontents}

```
