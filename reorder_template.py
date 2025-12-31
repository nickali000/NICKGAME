#!/usr/bin/env python3

# Simple script to reorder template conditions in parola_segreta.html
# Move "elif game.winner" check before "elif game.state == 'VOTING'"

import re

file_path = "/home/nicola/.gemini/antigravity/scratch/modular_platform/python-server/templates/parola_segreta.html"

with open(file_path, 'r') as f:
    content = f.read()

# Find and extract the GAME OVER section (from "elif game.winner" to before next "elif" or "{% endif %}")
# This is complex, so let's use a simpler approach: swap the order of the conditions

# Replace pattern: change line 104 from "elif game.state == 'VOTING'" to a placeholder,
# and line 162 from "elif game.winner" to "elif game.state == 'VOTING'",
# and the placeholder to "elif game.winner"

lines = content.split('\n')

# Find the lines
voting_line_idx = None
winner_line_idx = None

for i, line in enumerate(lines):
    if "elif game.state == 'VOTING'" in line and voting_line_idx is None:
        voting_line_idx = i
    if "elif game.winner" in line and winner_line_idx is None:
        winner_line_idx = i

print(f"Found VOTING at line {voting_line_idx + 1}")
print(f"Found WINNER at line {winner_line_idx + 1}")

# Extract the GAME OVER section (from winner_line_idx to end of that section)
# and the VOTING section (from voting_line_idx to winner_line_idx)

# Find where VOTING section ends (it's before the GAME OVER section starts)
voting_section_lines = lines[voting_line_idx:winner_line_idx]
winner_section_end_idx = None

# Find where GAME OVER section ends (look for next major comment or {% endif %})
for i in range(winner_line_idx + 1, len(lines)):
    if lines[i].strip().startswith('{% endif %}') and i > winner_line_idx + 10:
        winner_section_end_idx = i
        break

if winner_section_end_idx:
   winner_section_lines = lines[winner_line_idx:winner_section_end_idx]
   
   # Reconstruct: everything before VOTING, then WINNER section, then VOTING section, then everything after
   new_lines = (
       lines[:voting_line_idx] +
       winner_section_lines +
       voting_section_lines +
       lines[winner_section_end_idx:]
   )
   
   with open(file_path, 'w') as f:
       f.write('\n'.join(new_lines))
   
   print("✅ File reordered successfully!")
else:
    print("❌ Could not find end of WINNER section")
