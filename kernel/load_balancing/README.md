# load_balancing

This package only selects among already-running processes for one capability
or one shared resource.

It does not create processes, change process counts, grow thread pools, track a
second busy table, or perform automatic scale-in/scale-out. The process
reconciler owns explicit replica counts, and the thread runtime owns its fixed
startup policy.
