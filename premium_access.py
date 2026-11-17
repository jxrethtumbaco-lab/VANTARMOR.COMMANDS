"""Global slash-command access policy.

Ordinary commands remain free. Features requiring Premium enforce it in their
individual handlers rather than using a blanket tree-wide restriction.
"""
from discord import app_commands

FREE_COMMANDS = frozenset({"lockdown", "filtro-cuentas"})


class PremiumCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction):
        return True


__all__ = ["PremiumCommandTree", "FREE_COMMANDS"]
