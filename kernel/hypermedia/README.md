# hypermedia

English | [中文](README.cn.md)

The design follows HATEOAS: hypermedia as the engine of application state.

The source is Roy Thomas Fielding's dissertation, *Architectural Styles and the Design of Network-based Software Architectures* (University of California, Irvine, 2000; chair Richard N. Taylor). Chapter 5 defines REST. Section 5.1.5 names four uniform-interface constraints. The fourth is hypermedia as the engine of application state, after identification of resources, manipulation of resources through representations, and self-descriptive messages. Section 5.3.3 states the consequence: the application is an engine that moves from one state to the next by examining and choosing among the alternative state transitions in the current set of representations. That is the same act as choosing a link in a browser. The dissertation does not assume the user agent is a browser. An automated program can be that agent. Chapter: <https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm>. Full PDF: <https://ics.uci.edu/~fielding/pubs/dissertation/fielding_dissertation.pdf>.

The journal restatement is Fielding and Taylor, "Principled Design of the Modern Web Architecture," *ACM Transactions on Internet Technology* 2(2), May 2002, pages 115–150, <https://doi.org/10.1145/514183.514185>. An earlier conference version appeared at ICSE 2000. The name and the explanation are in the dissertation. The journal article is the peer-reviewed text of the same model.

In this directory a page is the current state. The facts say what it is now. The links say which transitions are open. The next step is chosen from those links. A relation that is not on the page cannot be followed.

## How linope uses it

The caller does not keep a second list of what is allowed. The current page is that list. After one step, the service returns the next page, and the links change with the state. The menu cannot drift from the state: an expired menu is rejected.

A file page has three states. The transitions are written in `representation_json.py` and carried out by `http_server.py`:

| Now | Transitions on the page | After the step |
|---|---|---|
| `resident` | `pin`, `swap`, and reading `content` | `pin` moves to `pinned`. `swap` moves to `swapped`. |
| `pinned` | only `self` and `content` | The body can still be read. It cannot be pinned again or swapped out. |
| `swapped` | only `self` and `admit` | `admit` returns to `resident`. |

After a swap the page has no `content` link. Reading the body returns `409` with `relation not offered`. After a pin the page has no `swap` link, and another swap is refused the same way. A successful POST writes the new state back to the ledger. The response is the new page.

The process page is `process_page.py`. `activity` is the current state. The links are the next steps allowed now:

| State | Extra links |
|---|---|
| `sleeping` | `stop`. The handle includes this start's mark, so an old stop cannot be used after that mark changes. |
| `with` | `with`, pointing at the process it is working with. |
| A living process that shares memory | `share`, pointing at the process that still holds the same memory. |
| A record that has a memory scope | `memory`, pointing at that memory. |

`closed` does not offer `stop`. `show` prints this page: the facts plus these links.

The memory page is `memory_page.py`. Each row is a link. The handle includes the current sequence. After another row is written, the sequence changes and the handle on the old page no longer matches. That is the same rule: once the state has moved on, the old transition is no longer valid.

The command menu a model may run is assembled in [`kernel/communication`](../communication/README.md). It uses the page and the links from here to put "start a process, load a tool, or ask" on the page the model sees. This directory supplies the page, the links, and the local HTTP service. The command that starts the service is [`kernel/command/screen`](../command/screen/README.md).

## Each script

`link.py`

One link: a relation name, the resource it points at, and a handle. A link with no handle cannot be followed.

`representation.py`

One document. `facts` are the facts. `links` are the links. A link names another resource. It does not include that resource's body.

`handle.py`

Turns the parts into one hexadecimal handle. A pid or an address by itself is not the right to follow. When a part such as the sequence changes, the handle changes.

`uri.py`

Writes the handle as a URI for this machine. A resource is `/resources/<handle>`. Content and actions have their own paths. The base must be `http` or `https`. Parsing accepts only the loopback hosts `127.0.0.1`, `localhost`, and `::1`. The URI does not contain a filesystem path.

`representation_json.py`

Turns a page into JSON. `self` and `content` are GET. `pin`, `swap`, and `admit` are POST. A file page offers only these relations:

| State | Relations |
|---|---|
| `resident` | `self`, `content`, `pin`, `swap` |
| `pinned` | `self`, `content` |
| `swapped` | `self`, `admit` |

`file_link.py`

Turns one file on disk into a page with a single `self` link. An empty handle cannot be followed.

`memory_page.py`

Turns memory rows into a page. Rows of the current question carry their words. Earlier rows carry an address, a kind, and a time. This page does not grant entry to those addresses. The pointer space remains [`kernel/scheduler`](../scheduler/README.md).

`process_page.py`

The process page that `show` prints. The facts say what the process is doing. The links list only the next steps allowed now.

`link_selector.py`

Picks links on a page. A selected link that carries a handle goes into `followed`. A link with no handle stays in `left`. This returns links only. It does not read memory, start a process, or call a tool.

`follow.py`

The old name. New code uses `link_selector`. A model turn is [`kernel/scheduler`](../scheduler/README.md).

`http_server.py`

Local HTTP. `serve_resources` listens only on `127.0.0.1`, `localhost`, and `::1`. An empty store path uses `file:.linope/resources.json`. A `memory:` store cannot start this service by itself. A second server for the same store is refused. A relation the page does not offer returns `409`, with the body `relation not offered`.

`__init__.py`

Marks this package as the local HATEOAS representations.

## Known Limitations and Deferred Work

- **HTTP serves the file store on loopback only** — there is no private-network bind, no dynamic auth, and no CAS or ETag.
