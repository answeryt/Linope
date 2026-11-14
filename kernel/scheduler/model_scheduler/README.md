# model_scheduler

This scheduler runs CPU-like model resources, not model processes. `Book`
keeps one shared ready, using, and waiting task line. At most one task per
configured model core can execute `model run` at a time. A task is not bound
to a core while it is ready; the next free core takes the front task.

File reads, searches, commands, and tool starts are waits. A waiting task
lends its core to the next ready task, and returns to the back of the shared
line when the wait ends. A model call that has started is allowed to finish.
Consecutive model requests stay on the same core until the task waits or ends.

`model cores <count>` sets the number of model cores, defaulting to one.
`model use` installs one provider card on every core. `model.py` calls
`capability.model.model_runtime` directly. Models have no pid and no
process-resource ledger entry.
