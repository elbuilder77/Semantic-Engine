import re

with open("ROADMAP.md", "r") as f:
    content = f.read()

total_items = 0
completed_items = 0
pending_items = 0
phases = {}
current_phase = None

for line in content.split('\n'):
    phase_match = re.match(r'^## (.+)$', line)
    if phase_match:
        current_phase = phase_match.group(1)
        phases[current_phase] = {'total': 0, 'completed': 0, 'pending': 0}
        continue

    task_match = re.match(r'^- \[(x| )\] (.+)$', line)
    if task_match and current_phase:
        status = task_match.group(1)
        phases[current_phase]['total'] += 1
        total_items += 1
        if status == 'x':
            phases[current_phase]['completed'] += 1
            completed_items += 1
        else:
            phases[current_phase]['pending'] += 1
            pending_items += 1

print(f"Total Completed: {completed_items}/{total_items} ({(completed_items/total_items)*100:.1f}%)")
for phase, stats in phases.items():
    if stats['total'] > 0:
        print(f"{phase}: {stats['completed']}/{stats['total']} ({(stats['completed']/stats['total'])*100:.1f}%)")
