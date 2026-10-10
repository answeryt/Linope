"""An MCP service: the MCP client plugin family running as tool processes.

Each member needs a ``load`` function to be discovered as a capability. The
first member takes the role ``mcp`` and answers ``tool`` requests; any
further member is ``mcp:<name>`` and must be named by role.
"""

from __future__ import annotations

from kernel.services.spec import MemberPlan, ServicePlan, ServiceSpec

ROLE = "mcp"
DEFAULT_MEMBER = "tools.mcp_tool_manager"
PREFIX = "tools.mcp"


class McpBlueprint:
    def plan(self, spec: ServiceSpec) -> ServicePlan:
        names = spec.members or (DEFAULT_MEMBER,)
        members: list[MemberPlan] = []
        for index, capability in enumerate(names):
            if not capability.startswith(PREFIX):
                raise ValueError(f"mcp 服务需要 {PREFIX}* 能力，收到 {capability!r}")
            if index == 0:
                members.append(
                    MemberPlan(
                        role=ROLE,
                        capability=capability,
                        changes=spec.changes,
                        replica_count=spec.replica_count,
                    )
                )
                continue
            members.append(
                MemberPlan(role=f"{ROLE}:{capability[len('tools.'):]}", capability=capability)
            )
        return ServicePlan(members=tuple(members), route={"tool": ROLE})
