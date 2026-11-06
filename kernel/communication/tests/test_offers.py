"""A page can name commands. Choosing them is the agent loop's work."""

from kernel.communication.page import CommandOffer, model_page


def test_a_page_can_carry_a_command_the_agent_loop_chose() -> None:
    page = model_page(
        [{"kind": "user", "content": "hello", "state": "asked"}],
        scope="chat",
        seq=1,
        commands=(CommandOffer("tool", "tools.read", pid=8),),
    )
    assert page.links
    assert any(link.relation == "tool:tools.read" for link in page.links)
