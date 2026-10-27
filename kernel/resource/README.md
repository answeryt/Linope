# resource/ — kinds, leases, and handles

English | [中文](README.cn.md)

`kernel/resource` is the process-resource relation:

`need → declaration → entity → lease → handle`

A process sees the handle, the kind, and the call parameters. The entity id stays on the grant inside this process. A handle has no quota. Whether a directory can be read or written is the room in [`kernel/environment`](../environment/README.md). Each process's account is [`kernel/process/resource_record.py`](../process/resource_record.py). On disk, [`kernel/process/ledger.py`](../process/ledger.py) stores a copy of that account.

## memory/

[`memory/`](memory/README.md) is the dictionary one memory entity holds.

`state.py` opens that dictionary as `{"address_space": {"scope": ...}}`. Rows live under `items`. The key of a row is its stored name: `message/0`, `task/0`, `artifact/0`, or `system`. `next` is the next number for `message`, `task`, and `artifact`. `seq` is one counter for the whole dictionary. `store.py` appends a row and joins named prompt files into the system row. `token_meter.py` sums tokens for text already stored. The sum is computed when asked.

Every process that holds the entity shares those stored names. A process's own `message/0` can point at a different stored name. That address list, and who may read or write, is [`kernel/scheduler`](../scheduler/README.md).

## Scripts

| Script | Role |
|---|---|
| `__init__.py` | The public names of this package, imported when first used |
| `resource_contract.py` | The registry of kinds |
| `definition.py` | What a capability needs, and the grant a process receives |
| `compile.py` | Turns one declaration into entity keys |
| `handle_view.py` | The serializable view of one process's grants |
| `lease.py` | The in-memory lease table, refcounts, and handle checks |
| `pool.py` | Binds a process: mints handles, takes leases, loads and unloads entities |

`__init__.py` exports definitions, grants, the context, leases, and the pool through `__getattr__`. The first use imports the module that defines the name. An eager import of the pool from this package would cycle while a process declaration is being imported, because `compile.py` refers to that declaration.

`resource_contract.py` is the only registry. `register` adds one kind: its name, the identity keys it requires, whether it may be shared, and optional open and close functions. A name that is not on the table is rejected by `require`. `validate_claim` refuses an identity that is missing a required key, and refuses `shared=True` when `allow_shared` is false. The built-in kinds are installed at import:

| Kind | Identity | Open |
|---|---|---|
| `memory` | `scope` | `memory.state.open_state`, so the entity is the address range named by its scope |
| `tool` | `id` | none |
| `sandbox` | `root` | none |
| `network` | `channel` | none |

`open_entity` calls the kind's open function. With no open function and no loader, it records `loaded: true`, the kind, and the identity. `close_entity` calls the kind's close function, or the loader's `unload` when a loader was passed.

`definition.py` holds the two shapes. `ResourceDefinition` is one kind a capability needs: the kind, whether it is required, and an optional entity id. `ResourceKind` names the four built-in kinds. `ResourceShareMode` is `exclusive` or `shared`. `ResourceGrant` is what one process was given: the entity id, the kind, the handle, the call parameters, and the share mode. `process_payload` keeps the handle, the kind, and the call parameters. `validate_grants` refuses duplicate handles. When a requirement names an entity id, grants are matched by that id and must have the same kind. Otherwise grants are matched by kind: every required kind must be present, and a kind the capability did not declare is refused.

`compile.py` runs `compile_declaration`. It pairs each claim with the capability's requirements, refuses a duplicate kind, a missing required kind, and a kind the capability did not declare. `entity_key` hashes the kind and the identity with SHA-256. Call parameters stay on the `CompiledResource` and never enter the key. A kind in this launch's `shared` list gets one key for that identity and `share_mode` `shared`. Any other claim gets a key that also includes the pid, and `share_mode` `exclusive`. Two exclusive claims with the same identity therefore get two entity keys. A kind that is only allowed to be shared stays exclusive until this launch names it. Handles are minted later.

`handle_view.py` is `ResourceContext`: the pid, the capability id, the grants, the time, and settings. `create` runs `validate_grants` and then builds that view. `payload` serializes it through each grant's `process_payload`. `from_payload` rebuilds the context with an empty entity id on every grant. `get` finds a grant by entity id. `get_handle` finds one by handle.

`lease.py` is `ResourceLeaseManager`, the in-memory table behind the pool. `acquire` creates a `ResourceEntity` on first use, appends a `ResourceLease`, and records the handle as active for that pid. The entity's `refcount` goes up by one. The first occupant is marked pending so the pool can load it. An exclusive acquire advances the fencing token and refuses when any lease is already active. A shared acquire keeps the current token and refuses when an exclusive lease is active. `authorize` refuses a missing handle, a handle that is not active, a handle that belongs to another pid, and a handle whose fencing token is older than the entity's. `release` drops every active lease of that pid, marks its handles released, and returns entities whose refcount reached zero while they were loaded. `revoke` marks one handle revoked and releases that pid's lease on its entity. `memory_named` refuses a lookup by scope. Reading a memory by name is approved in [`kernel/scheduler`](../scheduler/README.md).

`pool.py` is `ResourcePool`. `bind` takes the compiled claims, mints one handle per claim with `secrets.token_hex(16)`, and asks the lease table to acquire them. It then loads each entity whose refcount just left zero. Loading calls `open_entity`. The default loader is `RecordingLoader`, which records `loaded: true` and the identity. `release` asks the lease table which entities reached refcount zero and closes those through `close_entity`. `authorize` and `revoke` run on the lease table under the pool's lock. A listener receives `resource_load_succeeded`, `resource_load_failed`, `resource_unloaded`, and `handle_revoked`.

## Known Limitations and Deferred Work

- **`tool`, `sandbox`, and `network` open as a loaded mark** — those kinds register no open function, so `open_entity` records `loaded: true` and the identity. The call itself happens later, on `load`.
