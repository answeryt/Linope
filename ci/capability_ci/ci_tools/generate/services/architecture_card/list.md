# services: Agent = Service + Resources

## Vocabulary

- **Agent**: The final assembly of Service and Resources.
- **Service**: The only deployment boundary; it accepts a ProcessActivation and runs Processes.
- **Ingress**: Normalizes external input into a serializable Activation.
- **RunQueue**: Schedules Process and Task work with a lease and a fencing token.
- **ProcessStore**: Host-injected persistence interface for a Process run.
- **Resources**: The shared capacity pool of container resources and model resources.

## Structure

```
Agent
├── Service
│   ├── Ingress
│   ├── Worker
│   ├── Run Queue
│   ├── Process Store
│   └── Agent Assembly
└── Resources
    ├── Container Resources
    └── Model Resources
```

## This layer owns

- `Service`
- `ServiceBlueprint`
- `ServiceSpec`
- `ServiceHost`

## Architecture requirements

1. Agent is exactly Service plus Resources, not a persona or a process hierarchy.
2. Service is the only deployment boundary; one Service can run multiple Processes.
3. Ingress passes only a serializable ProcessActivation, not a live Process.
4. A worker drives the Process Runtime with a queue lease and a fencing token.
5. Store, Queue, and Ingress are host adapters and are not part of the Process definition.
6. OS processes, workers, queues, and deployment frameworks appear only in services.
7. The service layer only translates the spec, calls the existing create entry, delivers by role, and stops each member on shutdown.
8. Replica management and process picking are not in the service layer; they stay in process and load_balancing.
