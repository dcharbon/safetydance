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

A steps oriented library for Python.

## Motiviation

To enable a more fluent and fluid development experience through a steps-oriented programming environment with type-safe shared context
for the steps.

### Goals

* steps-oriented; do this, then do that, and onward
* steps are almost like natural langauge
* steps snap together thanks to loose-binding through shared context

Also, to enable the develpment of
[safetydance_test](https://gitlab.com/openteams/safetydance_test).

## Inspiration

Business Driven Development and [Cucumber](https://cucumber.io/).

## Example Usage

```{code-cell}
from dataclasses import dataclass
from safetydance import Context, ContextKey, script, step, step_data
import logging

logging.basicConfig(level=logging.DEBUG)

@dataclass
class Foo:
    bar: int

        
One = step_data(int)
Two = step_data(int, "Here's a description for ya!")
Logger = step_data(logging.Logger)
SomeFoo = step_data(Foo)

@step
def step_one(): # def step_one(context: Context):
    One = 1            # context[One] = 1
    SomeFoo = Foo(42)  # context[SomeFoo] = 42
    Logger = logging.getLogger("FooLog")

    
@step
def step_two():
    Two = 2  # context[Two] = 2 
    
    
@step
def step_with_args(arg1, arg2=None):
    print("arg1", arg1, "arg2", arg2)
    print(One, Two)
    step_one()
    
    
@script
def my_script():
    step_one()
    step_two()
    step_with_args("no keyword arg provided")
    step_with_args("keyword arg provided", arg2="this is the keyword arg")
    One = 3
    print(One)
    print(SomeFoo.bar)
    Logger.info(f"SomeFoo.bar: {SomeFoo.bar}")
    
my_script()
```


```{tableofcontents}
```
