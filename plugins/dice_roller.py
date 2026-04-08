PLUGIN_NAME = "dice_roller"
PLUGIN_DESCRIPTION = "Roll dice using standard RPG notation: 2d6, 1d20+5, 4d6 drop lowest, advantage/disadvantage"

async def run(query: str) -> str:
    import re, secrets

    q = query.lower().strip()

    # Parse XdY+Z notation
    dice_pattern = re.findall(r'(\d+)d(\d+)([+-]\d+)?', q)
    if not dice_pattern:
        # Simple "roll a d20" style
        simple = re.search(r'd(\d+)', q)
        if simple:
            dice_pattern = [('1', simple.group(1), '')]
        else:
            dice_pattern = [('2', '6', '')]  # default: 2d6

    advantage    = 'advantage' in q or 'vorteil' in q
    disadvantage = 'disadvantage' in q or 'nachteil' in q
    drop_lowest  = 'drop' in q and 'low' in q

    results = []
    for count_s, sides_s, mod_s in dice_pattern:
        count = min(int(count_s), 100)
        sides = min(int(sides_s), 10000)
        mod   = int(mod_s) if mod_s else 0

        rolls = [secrets.randbelow(sides) + 1 for _ in range(count)]

        if drop_lowest and len(rolls) > 1:
            dropped = min(rolls)
            used = sorted(rolls)[1:]
            total = sum(used) + mod
            results.append(
                f"🎲 {count}d{sides} drop lowest{f'+{mod}' if mod>0 else str(mod) if mod<0 else ''}:\n"
                f"   Rolls: [{', '.join(map(str, rolls))}] → dropped {dropped}\n"
                f"   Used: [{', '.join(map(str, used))}] → **Total: {total}**"
            )
        elif advantage or disadvantage:
            r2 = [secrets.randbelow(sides) + 1 for _ in range(count)]
            if advantage:
                chosen = rolls if sum(rolls) >= sum(r2) else r2
                label = "Vorteil (höher)"
            else:
                chosen = rolls if sum(rolls) <= sum(r2) else r2
                label = "Nachteil (niedriger)"
            total = sum(chosen) + mod
            results.append(
                f"🎲 {count}d{sides} ({label}):\n"
                f"   Set A: [{', '.join(map(str, rolls))}] = {sum(rolls)}\n"
                f"   Set B: [{', '.join(map(str, r2))}] = {sum(r2)}\n"
                f"   Gewählt: [{', '.join(map(str, chosen))}] → **Total: {total}**"
            )
        else:
            total = sum(rolls) + mod
            results.append(
                f"🎲 {count}d{sides}{f'+{mod}' if mod>0 else str(mod) if mod<0 else ''}:\n"
                f"   Rolls: [{', '.join(map(str, rolls))}]"
                + (f" + {mod}" if mod else "")
                + f"\n   **Total: {total}**"
                + (" 🎉 KRITISCH!" if sides == 20 and 20 in rolls else "")
                + (" 💀 Patzer!" if sides == 20 and 1 in rolls else "")
            )

    return "\n\n".join(results)
