### Request

> Assign this task to the best developer: rewrite the billing engine in Rust, 10 hours

**Selected workflow:** `WF009` - Employee Task Assignment  
**Routing:** heuristic (confidence 0.80) - matched: task, best, assign, developer, <task_description found>, <role found>  
**Parameters:** `task_description=rewrite the billing engine in Rust`, `role=developer`, `estimated_hours=10.0`, `employees_file=data/employees.csv` *(bundled sample)*

**Steps executed**

1. **success** - Understand task requirements - Skills: rust; priority medium; deadline none; 10h
2. **success** - compare employee skills - 0 employee(s) cover all required skills
3. **success** - check current workload - 0 suitable after workload check
4. **success** - rank candidates - Ranked 0 candidate(s)
5. **success** - select employee - No suitable employee - escalating
6. **success** - generate assignment summary - No suitable employee for this task - escalate to the manager. Priority medium, deadline none set.

**Conditions / decisions**

- task requirements: **skills: rust; role: developer; priority: medium** (deadline none; 10h)
- skill match: **0 of 8 employees have every required skill** (required: rust)
- capacity check: **0 employee(s) suitable** (free hours (pro-rated to the deadline) >= estimated hours)
- ranking weights: **skills 60% / capacity 40%** (standard weighting)
- no suitable employee: **ESCALATE to manager** (nobody has all skills AND capacity)

**Tools / API calls**

- employee_task_db.employees x1 (2 ms)

**Result (success)**

No suitable employee for this task - escalate to the manager. Priority medium, deadline none set.

_Escalation required_

| Item | Detail |
|---|---|
| Decision | No suitable employee - escalate to the manager |
| Why | Nobody is active, has every required skill, and has enough free capacity |
| Priority | medium |
| Deadline | none set |

_Task_

| Item | Detail |
|---|---|
| Task | rewrite the billing engine in Rust |
| Required skills | rust |
| Role filter | developer |
| Priority | medium |
| Deadline | none set |
| Estimated effort | 10 h |

_Closest candidates (not suitable)_

| Name | Role | Why not |
|---|---|---|
| Priya Nair | Frontend Developer | missing skill(s): rust |
| Sara Khan | Full Stack Developer | missing skill(s): rust |
| Karan Malhotra | Frontend Developer | not available (on leave); missing skill(s): rust |
