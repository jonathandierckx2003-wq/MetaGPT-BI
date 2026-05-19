from __future__ import annotations

from metagpt.actions.di.run_command import RunCommand
from metagpt.roles.di.role_zero import RoleZero
from metagpt.utils.common import any_to_str

_RUN_COMMAND_STR = any_to_str(RunCommand)


class BIBaseRole(RoleZero):
    """Base class for all BI pipeline agents.

    Overrides _observe() to strip other agents' RunCommand "I have finished the task"
    broadcast messages from memory before the LLM sees them. Without this filter,
    those broadcasts (published by Role.run() to every agent's buffer) pollute the
    receiving agent's memory and cause the LLM to call end prematurely (DEV-68).

    Why tracking pre-existing ids works:
    - _end() in RoleZero adds RunCommand messages directly to rc.memory (not via buffer).
      These represent the agent's own internal state and must be preserved.
    - Other agents' completion messages arrive via the shared buffer and are added to
      memory by super()._observe() when observe_all_msg_from_buffer=True.
    - By snapshotting RunCommand message ids BEFORE calling super(), we can identify
      and delete only the newly injected foreign messages afterward.
    """

    async def _observe(self) -> int:
        pre_existing_ids = (
            {id(m) for m in self.rc.memory.storage if m.cause_by == _RUN_COMMAND_STR}
            if self.observe_all_msg_from_buffer
            else set()
        )

        result = await super()._observe()

        if self.observe_all_msg_from_buffer:
            to_delete = [
                m for m in self.rc.memory.storage
                if m.cause_by == _RUN_COMMAND_STR and id(m) not in pre_existing_ids
            ]
            for m in to_delete:
                self.rc.memory.delete(m)

        return result
