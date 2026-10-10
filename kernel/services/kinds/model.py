"""A model service: one model capability answering prompt and context loads."""

from __future__ import annotations

from kernel.services.spec import MemberPlan, ServicePlan, ServiceSpec

ROLE = "model"
PREFIX = "model."


class ModelBlueprint:
    def plan(self, spec: ServiceSpec) -> ServicePlan:
        if len(spec.members) != 1:
            raise ValueError("model 服务只接受一个模型能力名")
        capability = spec.members[0]
        if not capability.startswith(PREFIX):
            raise ValueError(f"model 服务需要 {PREFIX}* 能力，收到 {capability!r}")
        return ServicePlan(
            members=(
                MemberPlan(
                    role=ROLE,
                    capability=capability,
                    changes=spec.changes,
                    replica_count=spec.replica_count,
                ),
            ),
            route={"prompt": ROLE, "context": ROLE},
        )
