"""An agent service: one model plus tools and context as peer processes.

Roles come from the capability prefix. ``model.*`` is the role ``model``,
``tools.*`` becomes ``tool:<name>``, ``context.*`` becomes ``context``.
Change clauses and the replica count go to the model member.
"""

from __future__ import annotations

from kernel.services.spec import MemberPlan, ServicePlan, ServiceSpec

MODEL = "model"
CONTEXT = "context"
TOOL_PREFIX = "tool:"


class AgentBlueprint:
    def plan(self, spec: ServiceSpec) -> ServicePlan:
        if not spec.members:
            raise ValueError("agent 服务至少要点名一个 model.* 能力")
        members: list[MemberPlan] = []
        route: dict[str, str] = {}
        for capability in spec.members:
            role = _role_for(capability)
            if role == MODEL:
                if MODEL in route.values():
                    raise ValueError("agent 服务只能有一个 model.* 成员")
                members.append(
                    MemberPlan(
                        role=MODEL,
                        capability=capability,
                        changes=spec.changes,
                        replica_count=spec.replica_count,
                    )
                )
                route["prompt"] = MODEL
                continue
            if role == CONTEXT:
                if CONTEXT in route.values():
                    raise ValueError("agent 服务只能有一个 context.* 成员")
                route["context"] = CONTEXT
            members.append(MemberPlan(role=role, capability=capability))
        if MODEL not in route.values():
            raise ValueError("agent 服务必须有一个 model.* 成员")
        shared = (
            tuple(member.capability for member in members)
            if spec.options.get("share")
            else ()
        )
        return ServicePlan(members=tuple(members), shared=shared, route=route)


def _role_for(capability: str) -> str:
    head, _dot, rest = capability.partition(".")
    if not rest:
        raise ValueError(f"能力名要写成 前缀.名字，收到 {capability!r}")
    if head == "model":
        return MODEL
    if head == "context":
        return CONTEXT
    if head == "tools":
        return TOOL_PREFIX + rest
    raise ValueError(f"agent 服务不认识 {head!r} 开头的能力: {capability!r}")
