from pathlib import Path


TARGET_CLASSES = ("HugReturnView", "ReactionChoiceView", "KillRoleplayView", "SpankReturnView")


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    for class_name in TARGET_CLASSES:
        start = source.find(f"class {class_name}(")
        if start < 0:
            continue
        next_class = source.find("\nclass ", start + 1)
        handler_end = source.find("\nasync def handle_reaction_command", start)
        possible_ends = [position for position in (next_class, handler_end) if position >= 0]
        end = min(possible_ends) if possible_ends else len(source)
        block = source[start:end]
        updated = []
        changed = False
        for line in block.splitlines():
            if "await interaction.response.edit_message(" in line and "embed=embed" in line and "view=self" in line:
                indentation = line[:len(line) - len(line.lstrip())]
                allowed = line.split("allowed_mentions=", 1)[1].rsplit(")", 1)[0] if "allowed_mentions=" in line else "discord.AllowedMentions.none()"
                updated.append(f"{indentation}await interaction.response.send_message(embed=embed, allowed_mentions={allowed})")
                updated.append(f"{indentation}await interaction.message.edit(view=self)")
                changed = True
            else:
                updated.append(line)
        if changed:
            source = source[:start] + "\n".join(updated) + source[end:]
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
