#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

"""File-backed named drivers: get a plug by socket and name.

This is an in-tree extension of :class:`~stevedore.driver.DriverManager`
for Open-Linux Hosts. Leaf plugins must not import this module; Host
loads it by file path.
"""

from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

from .driver import DriverManager
from .exception import NoMatches


class Lip:
    """Resolve ``(socket, name)`` through :meth:`DriverManager.from_file`."""

    def __init__(
        self,
        sockets: Mapping[str, Mapping[str, str]],
        *,
        repo: Path | str,
    ) -> None:
        self._repo = Path(repo)
        self._sockets = {
            str(socket): {
                str(name): str(path).replace('\\', '/')
                for name, path in plugs.items()
            }
            for socket, plugs in sockets.items()
            if isinstance(plugs, Mapping)
        }

    def get(self, socket: str, name: str) -> ModuleType:
        """Return the plug module registered as ``name`` on ``socket``."""
        plugs = self._sockets.get(socket) or {}
        relative = plugs.get(name)
        if not relative:
            raise NoMatches(f'No {socket!r} driver found, looking for {name!r}')
        manager = DriverManager.from_file(
            socket,
            name,
            self._repo / relative,
            module_name=f'lip_{socket}_{name}',
        )
        driver = manager.driver
        if isinstance(driver, ModuleType):
            return driver
        loaded = manager.extensions[0].plugin
        if isinstance(loaded, ModuleType):
            return loaded
        raise NoMatches(f'No {socket!r} driver found, looking for {name!r}')
