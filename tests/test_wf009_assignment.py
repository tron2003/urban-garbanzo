def run(agent, **p):
    return agent.run_workflow("WF009", p)


def test_sample_task_goes_to_best_react_developer(agent):
    r = run(agent, role="developer", priority="high")
    d = r.result.data
    assert r.status == "success" and d["decision"] == "assign"
    assert d["employee"] == "Priya Nair"                     # react 5 + javascript 5, 18h free
    assert d["priority"] == "high"
    assert d["ranking"][:2] == ["Priya Nair", "Sara Khan"]


def test_on_leave_employee_never_selected(agent):
    r = run(agent, role="developer")
    assert "Karan Malhotra" not in r.result.data["ranking"]
    notsuit = next(t for t in r.result.tables if t.title == "Not suitable")
    assert any("on leave" in row[2] for row in notsuit.rows if row[0] == "Karan Malhotra")


def test_escalates_when_nobody_has_the_skills(agent):
    r = run(agent, task_description="Rewrite the billing engine in Rust")
    assert r.status == "success" and r.result.data["decision"] == "escalate"
    assert "escalate" in r.result.summary.lower()
    assert any("rust" in " ".join(n["reasons"]) for n in r.result.data["near_misses"])


def test_escalates_when_skills_exist_but_capacity_does_not(agent):
    r = run(agent, task_description="Build a Django API with PostgreSQL", estimated_hours=30)
    assert r.result.data["decision"] == "escalate"
    assert any("insufficient capacity" in " ".join(n["reasons"]) for n in r.result.data["near_misses"])


def test_deadline_prorates_capacity(agent):
    # Sara has 10h free/week: fine for 8h with no deadline, not fine with only 3 working days (~6h)
    no_deadline = run(agent, task_description="Fix a React and Node bug", role="full stack", estimated_hours=8)
    assert no_deadline.result.data["employee"] == "Sara Khan"
    tight = run(agent, task_description="Fix a React and Node bug", role="full stack", estimated_hours=8, deadline="2026-10-09")
    assert tight.result.data["decision"] == "escalate"


def test_role_filter(agent):
    r = run(agent, task_description="Design the checkout screens in Figma", role="designer")
    assert r.result.data["employee"] == "Neha Verma"


def test_urgent_weights_capacity_more(agent):
    r = run(agent, priority="high")
    assert any("capacity 50%" in d.outcome for d in r.decisions)
    assert any("capacity 40%" in d.outcome for d in run(agent, priority="low").decisions)


def test_missing_requirements_ask(agent):
    agent.settings.allow_sample_defaults = False
    assert run(agent).clarification.missing == ["task_description"]
    assert run(agent, task_description="Please handle the thing").clarification.missing == ["employees_file"]
    r = run(agent, task_description="Please handle the thing", employees_file="data/employees.csv")
    assert r.status == "needs_input" and r.clarification.missing == ["required_skills"]


def test_bad_or_past_deadline_asks(agent):
    assert "past" in run(agent, deadline="2026-09-01").clarification.message
    assert "understand the deadline" in run(agent, deadline="whenever").clarification.message


def test_estimate_assumption_is_disclosed(agent):
    assert any("assumed 8 hours" in w for w in run(agent).warnings)


def test_broken_roster_fails_cleanly(agent, tmp_path):
    f = tmp_path / "e.csv"; f.write_text("name,skills\nA,react\n")
    r = run(agent, employees_file=str(f))
    assert r.status == "failed" and "missing column" in r.error
