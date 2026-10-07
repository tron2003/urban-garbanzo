def groups(agent, **p):
    return agent.run_workflow("WF006", p).result.data["groups"]


def names(g):
    return {r["name"] for r in g["records"]}


def test_same_sku_is_definite(agent):
    g = next(g for g in groups(agent) if "Samsung Galaxy S22 256GB" in names(g))
    assert g["confidence"] == "definite" and g["score"] == 1.0
    assert len(g["records"]) == 2


def test_sku_normalisation_cat_004(agent):
    g = next(g for g in groups(agent) if "Cotton T-Shirt Red M" in names(g))
    assert g["confidence"] == "definite"
    assert any("normalisation" in e for e in g["evidence"])


def test_similar_names_are_possible_not_definite(agent):
    gs = groups(agent)
    wallet = next(g for g in gs if "Leather Wallet Brown" in names(g))
    iphone = next(g for g in gs if "iPhone 13 (128 GB) - Black" in names(g))
    bottle = next(g for g in gs if "Aqua Stainless Water Bottle 750 ml" in names(g))
    for g in (wallet, iphone, bottle):
        assert g["confidence"] in ("high", "medium")
    assert wallet["confidence"] == "high" and iphone["confidence"] == "high" and bottle["confidence"] == "medium"


def test_variants_are_not_grouped(agent):
    all_names = [n for g in groups(agent) for n in names(g)]
    assert "Cotton T-Shirt Blue M" not in all_names          # colour differs
    assert "Cotton T-Shirt Red L" not in all_names           # size differs
    assert "Black Leather Wallet" not in all_names           # colour differs from the brown wallet pair
    assert "Bluetooth Speaker Mini" not in all_names         # same name, different brand


def test_unique_products_never_grouped(agent):
    all_names = [n for g in groups(agent) for n in names(g)]
    assert "Yoga Mat TPE 6mm" not in all_names and "LED Desk Lamp Adjustable" not in all_names


def test_group_counts_and_order(agent):
    gs = groups(agent)
    assert len(gs) == 5
    assert [g["confidence"] for g in gs][:2] == ["definite", "definite"]     # strongest first


def test_variant_decision_is_traced(agent):
    r = agent.run_workflow("WF006")
    assert any(d.name.startswith("similar names but conflicting") for d in r.decisions)


def test_too_few_rows_fails(agent, tmp_path):
    f = tmp_path / "c.csv"; f.write_text("sku,product_name\nA,One\n")
    r = agent.run_workflow("WF006", {"catalog_file": str(f)})
    assert r.status == "failed" and "at least two" in r.error


def test_no_duplicates_reports_cleanly(agent, tmp_path):
    f = tmp_path / "c.csv"; f.write_text("sku,product_name\nA,Red Kettle\nB,Blue Bicycle\n")
    r = agent.run_workflow("WF006", {"catalog_file": str(f)})
    assert r.status == "success" and r.result.data["groups"] == [] and "No duplicates" in r.result.summary
