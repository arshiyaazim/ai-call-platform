#!/usr/bin/env python3
from memory_manager import azim_profile_all
p = azim_profile_all()
if not p:
    print("No profile data")
else:
    total = 0
    for k, v in p.items():
        size = len(str(v))
        total += size
        print(f"  {k}: {size} chars")
    print(f"TOTAL profile: {total} chars")
