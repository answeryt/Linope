"""The system prompt joins identity, the protocol, then the tool guidance."""

from capability.prompt.prompt_load.prompt_load import system_prompt


def test_the_system_prompt_puts_identity_before_the_protocol() -> None:
    text = system_prompt()
    identity = text.index("You are the linope agent")
    protocol = text.index("The terminal is the window that reads commands.")
    tools = text.index("Use the read tool to view a text file.")
    assert identity < protocol < tools
    assert "\n\n" in text[identity:protocol]
    assert "\n\n" in text[protocol:tools]
