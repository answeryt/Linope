"""One capability as a service. The command line's default kind."""

from __future__ import annotations

from kernel.services.spec import MemberPlan, ServicePlan, ServiceSpec

ROLE = "capability"


class CapabilityBlueprint:
    def plan(self, spec: ServiceSpec) -> ServicePlan:
        if len(spec.members) != 1:
            raise ValueError("capability 服务只接受一个能力名")
        return ServicePlan(
            members=(
                MemberPlan(
                    role=ROLE,
                    capability=spec.members[0],
                    changes=spec.changes,
                    replica_count=spec.replica_count,
                ),
            ),
        )
