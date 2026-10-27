# The road ahead is long; I will search high and low.

English | [中文](linope_technical_report.zh.md)

This is a technical report on the Linope kernel. It introduces Linope's design, its way of building agents, and some of the technical detail, in plain language.

## Abstract

As more companies and developers build agents, one question is worth discussing:

How does the kernel of an agent system differ from the kernel of a traditional operating system?

I built the Linope agent kernel with that question in mind. Linope borrows ideas from traditional operating systems and, together with what is particular to agent systems, looks for a way of building agents that is different from the usual agent framework.

The report has two parts:

- Linope's design;
- Linope's way of building an agent.

I keep coming back to this: if a coding agent and a medical-advisor agent share one kernel, where does the difference actually sit?

Take a coding agent, swap some tools, change the prompts and the knowledge, and connect websites, software, or other services through MCP. Can that become a medical-advisor agent?

Today, Codex, Claude Code, and other agents already handle many kinds of work. They do not throw away their coordination when the task changes from coding to search, writing, or analysis. A developer usually adds a tool, adds a skill, or changes the knowledge source, and the agent can do something new.

That is possible because large language models keep getting more capable. We used to write a lot of code to control an agent's workflow. Models are now better at planning, understanding, and creating, and many complicated tasks can be broken up and carried forward by the model itself.

The open-source release of DeepSeek Harness makes the same point: an agent can gain a new capability through a plugin, without a new agent written for every new task.

So Linope's basic definition of an agent is:

Agent = kernel + capabilities.

In Linope, the kernel does not implement a particular model or tool. It loads an external capability into a peer capability process. That process can be an LLM, a search tool, a file tool, or some other service. The kernel should stay flexible.

Follow that further, and an agent OS kernel can borrow the way a traditional operating system is designed, and manage processes, threads, and resources, including:

- communication between processes;
- process lifetime;
- starting threads and controlling concurrency;
- load balancing;
- resource management;
- context management;
- network and sandbox management.

In an agent system those correspond to model calls, tool calls, reading context, communication between capability processes, and scheduling resources when many tasks run at once.

The capabilities inside the kernel coordinate the external capability processes. They do not implement each concrete capability.

## A different way to build an agent

The design above is:

Agent = kernel + capabilities.

The change Linope is exploring is more than putting the model and the tools into a few separate processes. It redefines what an agent is made of:

An agent is no longer a program whose insides are filled with a business workflow. It is a set of peer capability processes coordinated by the kernel.

In many agent frameworks, the agent is centered on one session or one agent instance. Model calls, tool calls, assembling context, compression, and the task loop all sit around that instance. Developers add capabilities by registering plugins, tools, and event listeners.

DeepSeek Harness is an example. It organizes plugins with Cordis, stores session facts as SessionEvents, projects the messages the model can see through a surface, and lets the Agent Loop drive turns, steps, model requests, and tool calls.

The relation is roughly:

plugin system
    ↓
Agent Loop
    ↓
SessionEvent log
    ↓
message projection
    ↓
model request

This makes a session easy to persist, replay, and restore. What the model sees can be rebuilt from the session log. When context is compressed, a summary message can replace an old message range while the original events remain.

The unit is still one complete agent session. Tools, models, and context managers are usually plugins hanging on that session or runtime. They do not, by themselves, have a resource ledger, an address space, and a lifetime.

Linope starts from a different place.

The kernel does not treat the model, the tools, and the context compressor as functions inside an agent. It treats each of them as a capability process:

- a model process is the ability to reason;
- a search process is the ability to search the web;
- a code-execution process is the ability to run something;
- a context-compression process is the ability to handle context.

None of them belongs to another by nature. The kernel only:

- creates and reclaims capability processes;
- manages the resources a process holds;
- passes requests between capability processes;
- chooses a process that is still alive and able to handle the task;
- manages resources such as memory, tool, sandbox, and network;
- schedules according to context pressure and process load.

The main difference between Linope and DeepSeek Harness is where the plugin and the capability sit.

In DeepSeek Harness, a plugin mainly extends one agent runtime. It registers services, events, and capabilities through Cordis, and the Agent Loop keeps the session moving.

In Linope, the capability itself is what the kernel schedules. The model and the tools each have a process identity, and each holds its own resource leases and ledger. The model looks at the page the kernel provides, sees which capability processes are still alive, and decides which one to call.

That is why Linope drops parent-child processes and the process tree.

Dropping parent and child does not mean capability processes have no relation. It means the relation is no longer "who started whom." Relations are made through resources, addresses, and communication, not inherited through a process tree.

For someone building an agent, the change is this:

People used to design an agent's workflow first, then fill that workflow with model, tool, and context-handling code.

In Linope, you first declare which capabilities and resources the agent needs, and you implement each capability as a process the kernel can start and call. Whether the next step is search, running code, asking another model, or reading earlier context is the model's choice from the current page. That is the flexibility I mentioned above. As models get more capable, more of the decisions should be left to the model. The kernel assists the model and supplies coordination. It does not fence in the model's thinking. (See Anthropic: "As models become more capable, agentic design will trend towards letting intelligent models act intelligently, with progressively less human curation." [https://www.anthropic.com/research/effective-context-engineering-for-ai-agents](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents))

Linope still has a procedure. Process lifetime, permission checks, reclaiming resources, communication, and request checks stay with the kernel. What changed is that the kernel no longer hard-codes a particular business flow. The kernel keeps execution safe and resources bounded. The model chooses and plans among capabilities.

A coding agent and a medical-advisor agent can use the same processes, resources, and scheduling. The difference comes from:

- the model in use;
- the tools attached;
- the knowledge sources;
- the system prompt and skills;
- the contents of memory;
- sandbox and network permission;
- the matching safety policy.

A medical setting is not finished by swapping a prompt. Medical knowledge, privacy, risk levels, handing off to a person, and auditing results should enter the system as their own capabilities or resources. Those changes do not require a new scheduling kernel.

That is the way of building Linope is after:

Describe what the agent needs with a resource declaration, provide those capabilities as peer processes, and let the kernel manage their lifetime, communication, and permission, instead of writing a separate coordination program for every kind of agent.

From this angle, DeepSeek Harness puts its weight on how to save and rebuild one agent session reliably. Linope puts its weight on how to split an agent into capability processes that can be isolated, shared, and scheduled.

Neither replaces the other. They look at different layers:

DeepSeek Harness:
session log → message projection → Agent Loop → model request

Linope:
capability process → resource lease → pointer space → kernel scheduling

What is "new" in Linope is not that an agent became a few processes. The unit of organization changed:

from "an agent that owns plugins" to "a set of capability processes coordinated by a kernel."

## Why treat a capability script as a process

A capability here means an external capability. Creating an external capability process gives the agent that capability.

For example:

- creating a model process gives the agent the ability to reason;
- creating a search process gives the agent the ability to search the web;
- creating a file-tool process gives the agent the ability to read and write files;
- creating a context-compression process gives the agent the ability to manage context.

I treat an external capability script as a process because, in a traditional operating system, the process is the unit of resource isolation.

Parent and child processes in a traditional operating system usually do a few jobs:

1. When a child starts, it can inherit the parent's address space, file descriptors, current directory, and environment.
2. A process group or a session can gather several processes so one signal or one stop applies to them together.
3. The parent can `wait` for the child's exit status, and the kernel can clear the matching process-table entry.

Those mechanisms fit how programs run on a traditional operating system. Capability calls in an agent system work differently.

A model may call a search tool while it is running. The search tool may call a file tool. The model may then start another model for a subtask. If all of those capabilities are fixed into a parent-child tree, the relations are frozen at start, and the system has less room to move.

Linope therefore drops parent-child processes and the process tree, and keeps capability processes as peers.

That has a few consequences.

### Process lifetimes stay separate

When a tool process crashes, the kernel cleans up that tool process. One capability failing does not take the others with it.

The model process can keep running. The other tool processes do not all have to exit. That matches how an agent actually runs: capability calls happen as the work proceeds, and one tool failure should not tear down the whole agent.

### Isolation does not spread by inheritance

When a peer process starts, it receives only what the kernel explicitly grants, for example:

- a resource handle;
- the resource kind;
- the call parameters;
- the configuration this capability needs.

It does not automatically receive another process's resource-entity ids, and it does not inherit every resource because some process is its "parent."

For environment variables, a capability receives only the secrets it declared. If a model capability declares an API key, the kernel copies that secret into the process environment. Other sensitive variables do not leak through process inheritance.

### Sharing has to be declared

Peer processes do not share memory, or any other resource, just because they belong to the same agent.

By default, memory with the same scope can still be compiled into separate exclusive resources. Processes use one resource entity together only when sharing is declared.

In the current implementation, `--share` applies to a resource kind that was already declared, such as memory. The model itself is not a resource kind registered on its own under `kernel/resource`. Model identity is passed through capability configuration and process settings. Sharing a model capability process and sharing a memory resource are different things. They are not the same lease.

### Calls go to processes that are alive now

Relations in a traditional process tree are usually fixed at creation. Tool calls in an agent are not.

A model may call search, then a code-execution tool, then another model. Whether a tool exists, is idle, or is still alive can change as the run proceeds.

A Linope model process does not look up tools through a fixed parent-child relation. It reads the kernel page, sees which capability processes are available now, and chooses.

The call relation follows the current state, not the shape of a process tree at creation.

### The resource ledger settles per process

Linope keeps a separate resource record for each pid.

Leases sit on that process's ledger:

- the process receives leases when it starts;
- it uses resources while it runs;
- it releases leases when it exits;
- when a resource's reference count reaches zero, the entity is unloaded.

A thread is only a way to run inside a process. It does not get its own resource ledger.

If resources were managed through a process tree, stopping one node would still leave the question of who owns the leases of the whole subtree. The ledger would be tied to whoever happened to start whom.

Linope binds resources to the process directly. Memory is the context resource the process uses, tool is the tool connection the process uses, and sandbox is the process's execution space. When the process exits, those grants are taken back.

## Communication between processes

If capability processes are peers, they cannot pass data automatically through a parent-child relation. They exchange tasks and results through the communication the kernel provides.

Communication between processes in Linope mainly answers three questions:

- how one process sends a task to another;
- how one process gets another's result;
- how the sender's resources and context stay out of the receiver.

When a model calls a tool, the model process can send a task to the tool process, and the tool process does not need the model process's whole memory. The receiver gets the current task and the resources it already owns.

When the tool finishes, the result comes back to the model process through the channel. The result can be written into the model's own memory, or returned to the model as part of the next page.

In `kernel/communication/channel.py`, communication is split into two kinds.

`MemoryChannel` is mainly for writing and reading the process's own memory. It holds user input, model results, tool results, and the context inside the process.

`ServiceChannel` is a service channel the caller has already opened. It provides:

- `send`: send one message to an address;
- `publish`: publish a message to a topic;
- `receive`: receive messages addressed here;
- `close`: close the channel.

The kernel does not decide which network transport to use, and it does not automatically open a connection for every capability process. The caller opens a channel, then communicates through it.

The communication mechanism and the capability implementation stay apart:

capability process:
handles the task

channel:
carries the task and the result

kernel scheduler:
chooses whom to talk to and checks access

A model process does not need the search tool's internals. It needs to know that some capability process can handle a search task. The kernel finds that process and hands the request over through the channel.

This also leaves room for remote communication later. Two capability processes can run on one machine and talk over a local channel. Later, one of them can run on another machine and talk over HTTP, RPC, or another protocol.

Communication between processes is not the same as sharing memory. A process can pass a task, and the receiver does not thereby receive the sender's context address space. The task body, the result body, and the right to read memory remain three separate questions.

## Threads: the unit of execution inside a process

In Linope, the process is the unit of isolation and of settling resources. The thread is the unit that runs a task inside the process.

One capability process may receive several requests at once. A model process may be waiting on several tool results. A search process may handle several searches at once.

Starting a new process for every request costs a lot to start and makes resource management heavier. Linope uses threads to handle tasks in parallel inside one capability process.

A thread mainly:

- takes a task from the process's input channel;
- runs one capability call;
- waits for a model, a tool, or the network;
- submits the result to the process's output channel;
- handles several tasks within the concurrency limit set for the process.

The relation is:

process:
owns resources, handles, the ledger, and the lifetime

thread:
uses resources the process already has, and runs a concrete task

A thread does not hold its own memory, sandbox, or network lease, and it does not keep its own resource ledger. Threads in one process share the resources that process already received. That matches the usual rule in a traditional operating system.

If one thread fails, that usually affects only the current request. If the whole capability process exits, the threads inside it stop, and the resources the process holds are released together.

Threads are for concurrency. Processes are for isolation and lifetime. Linope does not treat a thread as an isolation boundary, and it does not treat a thread as a capability of its own.

## Looking at an agent as a service

Besides looking at an agent as processes, you can look at an agent as a service.

A process and a service are not two competing ideas. They sit at different layers:

process:
how the agent runs inside the system

service:
how other processes, agents, or outside applications reach it

An agent can run locally as a capability process and, at the same time, appear as a service. The process has a pid, resource leases, and runtime state. The service has an address, a calling protocol, a description of what it can do, and a lifetime interface.

Once an agent is a service, it is no longer only a script waiting for a model to call it. It can be a component that other systems discover, call, and combine.

A medical agent can be a medical question-answering service that other agents call. A coding agent can be a code-analysis and writing service that a scheduler calls. A search agent can be a search service shared by several model processes. A general enough agent might be made of several agent services, shaped to the work. One day, might we split and refine agents by the work, the way we split microservices, and end up with a microservice version of agents? I take up that guess below.

This lines up with where some agent projects on GitHub are going.

AgentScope Runtime exposes an agent as Agent-as-a-Service, with a streaming API, a tool sandbox, observability, and local, Kubernetes, and serverless deployment. The emphasis is not "an agent is one function call." It wraps the agent runtime as an application that can keep serving.

The A2A project goes further and treats communication between agents as an open protocol. A2A lets agents from different frameworks, companies, and servers discover each other's capabilities, agree on how to interact, and collaborate through JSON-RPC over HTTP(S), streaming, or asynchronous notification.

A2A is particular about keeping an agent's internal state opaque. The caller does not need the other agent's model, internal memory, or tools. An Agent Card is enough to learn what it offers, how to connect, and which interactions it supports.

That lines up with Linope in places:

Linope process:
capability, resources, handle, pid

Linope service:
address, what the service can do, protocol, call relation

A2A:
Agent Card, task protocol, collaboration between remote agents

These projects are not the same implementation. AgentScope Runtime cares about running agents in production. A2A cares about agents from different places working together. Linope cares about processes, resources, and scheduling at the kernel.

Together they say one thing:

An agent is moving from a program that can only be called from the inside to a service that other systems can discover and call.

From that angle, a Linope capability process can be what a service runs on. One service can be one capability process, or several of them together. The kernel handles the process lifetime, resource leases, and load balancing behind the service. The service interface is what the outside calls.

## Communication between services

Communication between processes happens among capability processes the kernel manages. Communication between services happens between two services that stand on their own.

The difference is that service-to-service communication may cross machines, and the two sides may not share one process manager. Between services you may have:

- network delay;
- service discovery;
- authentication;
- permission control;
- request timeouts;
- retries;
- asking for task status;
- streaming output;
- asynchronous callbacks;
- version compatibility.

So communication between services is not "process communication moved onto the network." It needs a clearer service contract.

A service at least has to say:

- who it is;
- which tasks it can finish;
- what input it accepts;
- what result it returns;
- whether a task may run for a long time;
- whether it can stream results;
- how to ask for task status;
- how to cancel a task;
- what permission it needs.

Linope's current `ServiceChannel` already points in that direction: the caller talks to the service with `send`, `publish`, and `receive`, and whether the transport is a local channel, HTTP, RPC, or something else can be decided outside.

The kernel manages scheduling and resources. The communication layer moves data between services.

## HATEOAS and Linope's hypermedia links

How a service tells a caller "what you can do right now" matters.

One common approach hard-codes every interface in the client:

the client knows:
/search
/tool
/ask
/start
/stop

The problem is that the client must know every operation in advance. If the service is down, permission changes, or the service adds an operation, the client may still call the old interface.

Linope does it the other way: the current page tells the model, or the caller, which actions are available now.

In `kernel/hypermedia`, a page is facts and links. A memory page can include:

- the state of the current memory;
- the current turn;
- addresses of earlier content;
- links for memory that can be read;
- tools that can be called;
- models that can be asked;
- capability processes that can be started;
- the entry for a final answer.

`memory_page()` builds the memory links. `model_page()` adds links for tools, models, and starting a capability, from the processes that are alive and from the permissions in force.

The design is inspired by HATEOAS.

HATEOAS is a constraint in the REST architectural style. The name is:

Hypermedia As The Engine Of Application State

The idea is that the client does not need to know every possible state transition in advance. It discovers the next step from the hypermedia links the service returns.

Two references:

1. Roy Fielding's dissertation, especially the constraint "Hypermedia as the engine of application state": [https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm](https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm)
2. RFC 8288, "Web Linking," which defines how a Web link, a link relation, and a target resource are expressed: [https://www.rfc-editor.org/rfc/rfc8288](https://www.rfc-editor.org/rfc/rfc8288)

`kernel/hypermedia` is not a complete REST service, and it does not hand the model a web page to click. What it takes from HATEOAS is this: the current resource state supplies the relations and entries that can be tried next.

A model page might tell the model:

memory/message/0
tool:search
ask:model-02
process start tools.ddgs
answer

The model does not have to memorize every tool command. It chooses an available link on the current page.

Linope uses this for a few reasons.

First, less scheduling logic hard-coded in advance.

If the model and the client hard-code every tool and process, every new capability means editing the prompt, the client, or the scheduler.

When the page offers the links, the kernel can show a new capability as it appears. The model has to understand the current page. It does not have to know every capability that might exist.

Second, the page follows the run as it is now.

A tool process may have exited. A model may be busy. A capability may not have been granted. A service may be unusable because of permission. Those states can decide whether the matching link appears. The page shows what can be tried at this moment, not every capability the system has ever had.

Third, discovery and execution stay apart.

A link on the page is an entry that might be executed. It is not the final grant.

Even if the model sees an address, the scheduler still checks:

- whether the process exists;
- whether the resource exists;
- whether this process has the permission;
- whether the selector lies in the pointer space;
- whether the handle is still valid.

A HATEOAS-style page tells the model what it may try. The kernel's permission checks decide whether it is actually allowed.

Fourth, it can grow into services.

In local process mode, a link can point at a capability process, a memory address, or a kernel command.

In a later service mode, a link can point at a remote service, a task resource, or an A2A operation.

A remote medical agent might return:

self
capabilities
task
status
cancel
result

The caller does not need to know how many processes sit inside the service. It follows the link relations and finishes the task. That separates the client from the server.

Fifth, less context spent up front.

The older habit is to put every tool description, all of the history, and every available command into the model's context.

A Linope page offers the addresses and actions that matter now. When the model needs history, it reads that memory address. When it needs a tool, it follows the tool relation.

That matches a rule in context engineering:

Do not put every possible piece of information into the context at once. Provide what the current decision needs, when it is needed.

A link is not a security grant. A model can forge an address string, and that does not give it the resource. Every real read and every real call still goes through the selector check, the pointer-space check, and the resource-handle check in the Linope kernel.

## Agent services, and a later try at microservices

Above I said a general enough agent might be made of several agent services, shaped to the work.

Linope today mainly runs as local processes under kernel scheduling. Later, a capability process can be wrapped as a service of its own, with:

- its own service address;
- its own version;
- its own resource quota;
- its own place of deployment;
- its own observability;
- its own upgrade cycle.

The call might grow from:

model process → kernel → tool process

to:

model service → service discovery → tool service

The kernel can still own resources and permission, while the bytes move over HTTP, RPC, A2A, or another protocol.

Turning an agent into a service is not "add an HTTP interface to the process we already have." A real microservice split still has to deal with:

- how a task resumes after the network drops;
- whether sending a request twice causes the side effect twice;
- how service versions stay compatible;
- how to ask about a task that runs for a long time;
- how a remote service authenticates;
- which side owns memory;
- whether tool results need to be stored;
- who retries when a service fails;
- how trace and audit information pass between services.

The more accurate statement is:

Linope splits an agent into peer capability processes, and keeps a path toward agent microservices through resources, communication, service descriptions, and hypermedia links.

The process is what the service runs on this machine. The service is the boundary through which a capability is reached.

Both can exist at once:

agent service
    ↓
one or more capability processes
    ↓
resource leases, threads, tools, and memory

Later, the transport can change without redesigning the capability. The capability gains a new service provider and a new transport implementation.

## How Linope designs resources

Resource management is a large part of an operating-system kernel.

Resources in a traditional operating system usually include:

- CPU;
- memory;
- I/O devices;
- disk;
- network devices.

Linope sits on top of that operating system. The CPU, the GPU, the machine's real memory, and the disk stay with the host operating system. Linope uses them through the processes, files, network, and system calls the host provides.

That follows "do not rebuild the wheel."

The Linope kernel cares about resources that belong to an agent:

- memory;
- tool;
- sandbox;
- network.

These are not hardware. They are capability resources an agent has to request, isolate, share, and reclaim while it runs.

The basic relation is:

need → declaration → entity → lease → handle

A capability first declares which resources it needs. The kernel creates or obtains a resource entity from that declaration, opens a lease for the concrete process, and issues a handle.

What the process actually sees is the handle, the resource kind, and the call parameters, not the kernel's full internal structure.

The resource entity and the process ledger are separate:

- the entity holds the live state;
- the lease says who is using the resource;
- the process ledger records which resources a pid holds;
- the handle is how a call is checked for whether the caller may still enter.

The kernel does not have to change process management for every new resource. Register the new kind in the resource contract, and the existing entity, lease, handle, and ledger machinery can be reused.

## Memory: the agent's context space

If a token is the unit of memory in an agent OS, a model's context window is like the memory a traditional operating system can still give out.

How much one model call can carry depends on the context length the model allows. A longer context lets the model see more history. When the context is full, something has to be cut, compressed, or handed to another process.

A token is not Linope's memory itself.

More precisely:

- memory stores the context;
- context is what is projected out of memory and prepared for the model;
- a token measures how much context space that content takes;
- the context limit is the longest context the model will accept.

So Linope's memory is closer to "context memory" than to a database, a vector database, or a permanent memory system.

### Compared with a framework centered on a session log

DeepSeek Harness again: it stores one agent session as an append-only SessionEvent log. User messages, model messages, and tool results become events.

A surface then projects the events that may enter the model context into a message list, and `deriveMessages()` rebuilds the model history.

The relation is:

SessionEvent log
    ↓
surface projection
    ↓
deriveMessages()
    ↓
model message history

When context is compressed, a summary message replaces the old message range. The original events stay in the log. The next time the model looks, it sees the replaced surface.

That emphasis is:

- persisting the session log;
- replaying a request;
- being able to follow a compression;
- rebuilding the model context in a determined way.

Linope is after a different question.

Memory in Linope is not another spelling of the session log. It is a kernel resource with an identity, access permission, virtual addresses, and a lifetime.

The two can be put like this:

centered on a session log:
event log → message projection → full context → compression replaces a range

Linope:
resource lease → pointer space → selector authorization → read when needed

The first answers "how do we reliably save and rebuild one agent session." The second answers "how do peer capability processes isolate, share, and read context."

## Memory is a resource

In a traditional operating system, a process does not own the machine's physical memory. It receives a managed address space from the operating system.

Linope takes a similar approach.

Memory is registered as a resource kind. The caller supplies a scope, for example:

memory=chat
memory=medical-session
memory=coding-task

That scope is the name of one logical memory space. The kernel builds a `resource_id` from the resource kind and the identity, then opens a lease and a handle for the process.

A model does not own memory by nature. In the current project, a model capability declares a network resource by default, and a memory resource is attached when needed with `--with memory=chat`.

After that:

- a model can have no memory and take a one-shot input;
- a model can have its own memory;
- several models can explicitly share one memory;
- a context-compression capability can use memory as its own process.

The kernel does not care whether the memory holds a coding conversation, a medical consultation, or a search task. It creates the resource, assigns permission, and manages the lifetime.

## A pointer: the way into context

Linope memory is not a dictionary a process can read directly. The process first needs a pointer to that memory.

In `kernel/scheduler/memory_space.py`, a memory pointer contains:

scope       the memory's name
resource_id the underlying resource entity
classes     the classes this pointer may enter
handle      the handle the process holds

A pointer is an address and a range of access.

For example:

scope = chat
classes = ("message", "artifact")

means this process may enter messages and tool results in chat, and may not enter task or system.

The kernel builds the process's own pointer space from the resource grants the process already holds.

Knowing a memory's name is not enough. Access goes through only when all of these hold:

1. the process holds that memory;
2. the scope is in its pointer space;
3. the target class is allowed;
4. the resource handle is still valid.

## Memory stores the original content

When a new memory opens, it starts with one address-space record:

address_space:
    scope: chat

As the process works, that grows into a dictionary, mainly:

- `items`: the messages, tasks, and tool results actually stored;
- `next`: the next number for each class;
- `seq`: a counter that increases across the whole memory;
- `system`: the system prompt;
- `prompt_files`: prompt files already loaded.

One row usually has:

- `class`: message, task, artifact, or system;
- `kind`: user, model, tool, or other;
- `content`: the original content;
- `time`: when it was written;
- `seq`: its order in the whole memory;
- `state`: for example asked, resulted, rejected, or answered.

Different content goes into different classes:

- user input and model output are message;
- a tool result is artifact;
- another scheduling task is task;
- the system prompt is system.

For example:

message/0  → the user's question
message/1  → the model's answer
artifact/0 → a tool result
task/0     → a task handed to another process

The number is not global. `message/0` and `artifact/0` can exist together because they are different classes.

What orders rows across classes is `seq`. Memory can be read by class, and it can also be put back into model messages in time order.

The system prompt is not simply pasted onto every request. Prompt files written through `write_prompt` are kept in `prompt_files` and composed into one system row at the positions given.

A prompt file with the same name is replaced. It is not appended forever.

## Why each process has its own address table

Several processes can share one memory entity and still not share one local address table.

Process A joins the memory first:

underlying:
message/0 = the first message

process A:
message/0 → message/0

Then process B joins, and process A writes another message:

underlying:
message/0 = the first message
message/1 = the second message

process A:
message/0 → message/0
message/1 → message/1

process B:
message/0 → message/1

A's `message/1` and B's `message/0` point at the same real record.

Linope distinguishes:

- `address`: the local address the process sees;
- `real`: the record's name inside memory;
- `scope`: the name of the resource space;
- `resource_id`: the entity id inside the kernel.

That is close to a virtual address space. Several processes can map the same underlying resource and still use different virtual addresses.

## Memory has an address space of its own

If there were only one shared dictionary, and every process used `message/0` and `message/1` directly, there would be a problem.

Processes join at different times, and they are allowed to see different classes. If every process used the underlying numbers directly, a process that joins later would see every earlier record, and the isolation would be gone.

Linope splits memory into two layers:

The first layer is the memory entity, which stores the real content.

The second layer is the process's own pointer space, which decides which memory this process may enter and which classes it may see there.

For example:

message/0
message/0-10
artifact/0
chat/message/0

Among those:

- `message/0` is message 0 in this process's address space;
- `message/0-10` is the message range this process can see;
- `chat/message/0` enters the memory named chat through its scope;
- the scope name itself is not permission. A read is allowed only when the process actually holds a pointer to chat.

## How the model uses pointers

In page mode, the model does not receive the full history at the start.

`memory_page()` puts the current turn on the page. Earlier content is shown as an address, a type, and a time:

message/0
artifact/0
message/1

If the model needs an earlier message, it makes a `MemoryRead` request. The read happens after permission passes.

The path is roughly:

the model asks for message/0-3
    ↓
authorize_selector()
    ↓
PointerSpace.require()
    ↓
memory_contents()
    ↓
the next page

An address on the page is an entry that may be read. It is not a grant. The grant stays with the scheduler.

Reading on demand follows one rule:

More context is not always better. Send the model what helps the decision in front of it.

History does not fill the context unconditionally. The model picks the addresses the task needs, and the kernel checks whether it may read them.

One model turn goes roughly like this:

1. The user's question is written into memory.
2. The scheduler builds the current page.
3. The model chooses to read history, call a tool, ask another model, or answer.
4. The scheduler checks the model's request.
5. Actions that pass are carried out.
6. A tool result, or another process's result, is written back into memory.
7. The next page is built.
8. This continues until the model gives a final answer.

Reading memory does not start a tool or a process. A read is still a read. The scheduler starts a tool, a capability process, or a question to another model only when the model asks for that.

## Context compression is a capability, not memory itself

When to compress, and whether a successful compression replaces the original context, is the host's policy.

That is a basic tradeoff in Linope:

The kernel manages the context resource and the access boundary. The compression capability decides how to rewrite the context.

The kernel should not decide, for a particular agent, which memories are worth keeping.

For a coding agent, file paths, compiler errors, and test results may matter most. For a medical advisor, history, medication, and time order may matter most. The compression rule belongs to a capability. It should not be hard-coded in the kernel.

## The lifetime of memory

Memory's lifetime follows the resource lease, not a fixed parent-child tree.

When a process starts:

1. It declares that it needs memory.
2. The kernel compiles a resource entity from the scope.
3. The resource pool creates or obtains the memory.
4. The process receives a handle.
5. The resource ledger and the address space are set up.
6. The process starts reading and writing.

When a process exits:

1. The handle is released.
2. The memory's reference count goes down.
3. If other processes still share it, the memory stays.
4. If the reference count reaches zero, the resource is unloaded.

In the current project, the ledger stores the resource account, for example:

- pid;
- resource kind;
- `resource_id`;
- handle;
- identity;
- lease status.

It does not store the message text.

The body of memory is a runtime resource, not permanent data in the ledger file. Linope's memory today is context memory managed by the kernel, not a database for long-term knowledge.

If user profiles, project knowledge, or medical records later need to last across sessions, a database, a vector store, or a filesystem can be a new capability resource, offered to the agent through a tool process.

## Summary

Linope's design sits in a few layers.

At the capability layer, models, tools, and context compressors are peer capability processes.

At the process layer, each capability process has its own lifetime, pid, and resource ledger.

At the resource layer, the kernel manages memory, tool, sandbox, and network through entities, leases, handles, and reference counts.

At the context layer, memory stores the original content, the pointer space manages access, a selector describes a read range, and pages let the model fetch history when it needs it.

At the scheduling layer, the kernel routes requests from the processes that are alive, the resource state, context pressure, and concurrency.

Linope and a framework centered on a session log are after different things. The latter is mainly about how a session is persisted, projected, and rebuilt. Linope goes on to split an agent into capability processes the kernel can isolate, share, and schedule.

What Linope proposes is not only another agent framework. It is another way to build an agent:

An agent is no longer one session with many plugins bound to it. It is a set of capability processes managed by a kernel. The model plans and chooses capabilities. The kernel handles processes, resources, permission, and communication.
