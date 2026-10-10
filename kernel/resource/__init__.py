"""Resource domain shared by capability processes and in-process runtimes.

The package uses lazy exports because ``kernel.resource.compile`` references the
process declaration module. Eagerly importing the pool here would create a
cycle while a process declaration is being imported.
"""

__all__ = [
    "HandleRevocation",
    "HandleStatus",
    "LeaseStatus",
    "RecordingLoader",
    "ResourceContext",
    "ResourceDefinition",
    "ResourceEntity",
    "ResourceGrant",
    "ResourceKind",
    "ResourceLease",
    "ResourceLeaseManager",
    "ResourcePool",
    "ResourceShareMode",
    "validate_grants",
]


def __getattr__(name: str):
    if name in {
        "ResourceDefinition",
        "ResourceGrant",
        "ResourceKind",
        "ResourceShareMode",
        "validate_grants",
    }:
        from kernel.resource import definition

        return getattr(definition, name)
    if name == "ResourceContext":
        from kernel.resource.context import ResourceContext

        return ResourceContext
    if name in {
        "HandleRevocation",
        "HandleStatus",
        "LeaseStatus",
        "ResourceEntity",
        "ResourceLease",
        "ResourceLeaseManager",
    }:
        from kernel.resource import lease

        return getattr(lease, name)
    if name in {"RecordingLoader", "ResourcePool"}:
        from kernel.resource import pool

        return getattr(pool, name)
    raise AttributeError(name)
