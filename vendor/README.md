# vendor/cyclic

This directory contains the Cyclic Programming interpreter,
used as a physics engine for energy-conserving repurposing actions.

Source repository:
https://github.com/JinnZ2/Cyclic-programming

## How to install

### Option A – Git submodule (recommended)


### Option B – Manual copy
Download `cyclic_interpreter.py` from the repository above
and place it in this directory.

## Usage in this project

The Cyclic interpreter is imported ONLY by `cyclic_repurpose_adapter.py`.
All other modules use the adapter. This keeps the two projects
separate and prevents accidental cross-contamination.

The adapter provides a fallback resource tracker if the interpreter
is not available, so the repurpose controller works either way.
