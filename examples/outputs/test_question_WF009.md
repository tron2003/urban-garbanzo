### Request

> Assign this urgent task to the best available developer.

**Selected workflow:** `WF009` - Employee Task Assignment  
**Routing:** heuristic (confidence 0.86) - matched: task, best, assign, available, <role found>, <priority found>  
**Parameters:** `role=developer`, `priority=high`, `task_description=Fix the checkout page bug in the React storefront: the pay button is unresponsive on mobile Safari. Likely a JavaScript event-handling issue.` *(bundled sample)*, `employees_file=data/employees.csv` *(bundled sample)*

**Steps executed**

1. **success** - Understand task requirements - Skills: javascript, react; priority high; deadline none; 8h (bundled sample task)
2. **success** - compare employee skills - 3 employee(s) cover all required skills
3. **success** - check current workload - 2 suitable after workload check
4. **success** - rank candidates - Ranked 2 candidate(s)
5. **success** - select employee - Selected Priya Nair
6. **success** - generate assignment summary - Assign to Priya Nair (Frontend Developer). Priority high, deadline none set.

**Conditions / decisions**

- task requirements: **skills: javascript, react; role: developer; priority: high** (deadline none; 8h (assumed))
- skill match: **3 of 8 employees have every required skill** (required: javascript, react)
- capacity check: **2 employee(s) suitable** (free hours (pro-rated to the deadline) >= estimated hours)
- ranking weights: **skills 50% / capacity 50%** (urgent tasks weight free capacity more)
- assignee: **Priya Nair (Frontend Developer)** (score 0.72)

**Tools / API calls**

- employee_task_db.employees x1 (1 ms)
- ranking_logic.rank x1 (0 ms)

**Warnings**

- No effort estimate given - assumed 8 hours (one working day).

**Result (success)**

Assign to Priya Nair (Frontend Developer). Priority high, deadline none set.

_Recommended assignment_

| Item | Detail |
|---|---|
| Employee | Priya Nair (Frontend Developer) |
| Reasoning | Priya Nair has javascript (5/5), react (5/5), 18h free this week (22/40h booked, 3 open task(s)), and scored highest (0.72) among 2 suitable candidate(s). |
| Priority | high |
| Deadline | none set |

_Task_

| Item | Detail |
|---|---|
| Task | Fix the checkout page bug in the React storefront: the pay button is unresponsive on mobile Safari. Likely a JavaScript event-handling issue. |
| Required skills | javascript, react |
| Role filter | developer |
| Priority | high |
| Deadline | none set |
| Estimated effort | 8 h |

_Candidate ranking_

| # | Name | Role | Skill score | Free | Total |
|---|---|---|---|---|---|
| 1 | Priya Nair | Frontend Developer | 1.00 | 18h | 0.72 |
| 2 | Sara Khan | Full Stack Developer | 0.80 | 10h | 0.53 |

_Not suitable_

| Name | Role | Why not |
|---|---|---|
| Aarav Mehta | Senior Developer | missing skill(s): javascript, react; insufficient capacity: ~6.0h available vs 8h needed |
| Rohan Gupta | Backend Developer | missing skill(s): javascript, react; insufficient capacity: ~2.0h available vs 8h needed |
| Vikram Singh | DevOps Engineer | role 'DevOps Engineer' does not match 'developer'; missing skill(s): javascript, react |
| Meera Joshi | QA Engineer | role 'QA Engineer' does not match 'developer'; missing skill(s): react |
| Karan Malhotra | Frontend Developer | not available (on leave) |
| Neha Verma | UI Designer | role 'UI Designer' does not match 'developer'; missing skill(s): javascript, react |
