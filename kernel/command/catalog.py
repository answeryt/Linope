"""The only place a new command is registered."""

from __future__ import annotations

from kernel.command.protocol import CommandSpec


def specs() -> tuple[CommandSpec, ...]:
    """Return every command. Imports stay inside the function so parsing one command does not build the table."""
    from kernel.command.ask import SPEC as ask
    from kernel.command.call import SPEC as call
    from kernel.command.channel import SPEC as channel
    from kernel.command.env import SPEC as env
    from kernel.command.file import SPEC as file
    from kernel.command.layout import SPEC as layout
    from kernel.command.load import SPEC as load
    from kernel.command.resources import SPEC as resources
    from kernel.command.room import SPEC as room
    from kernel.command.service import SPEC as service
    from kernel.command.share import SPEC as share
    from kernel.command.start import SPEC as start
    from kernel.command.store import SPEC as store
    from kernel.command.terminal import SPEC as terminal
    from kernel.command.thread import SPEC as thread

    return (
        ask,
        call,
        channel,
        env,
        file,
        layout,
        load,
        resources,
        room,
        service,
        share,
        start,
        store,
        terminal,
        thread,
    )
