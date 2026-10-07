# Example runs

LLM mode: **offline** (offline heuristic router + template generation)

## 1. The workbook's own Test_Questions sheet

| Workflow | Request | Selected | Routing | Outcome |
|---|---|---|---|---|
| WF001 | Which products need restocking? | WF001 OK | heuristic | completed ([details](test_question_WF001.md)) |
| WF002 | Find products where vendor price differs by more than 10%. | WF002 OK | heuristic | completed ([details](test_question_WF002.md)) |
| WF003 | Process this vendor spreadsheet and show invalid rows. | WF003 OK | heuristic | completed ([details](test_question_WF003.md)) |
| WF004 | Generate SEO content for this product. | WF004 OK | heuristic | completed ([details](test_question_WF004.md)) |
| WF005 | Where is order ORD-1001? | WF005 OK | heuristic | completed ([details](test_question_WF005.md)) |
| WF006 | Find likely duplicate products in the catalog. | WF006 OK | heuristic | completed ([details](test_question_WF006.md)) |
| WF007 | Create a campaign brief for the new collection. | WF007 OK | heuristic | needs_input ([details](test_question_WF007.md)) |
| WF008 | Classify these keywords and map them to pages. | WF008 OK | heuristic | completed ([details](test_question_WF008.md)) |
| WF009 | Assign this urgent task to the best available developer. | WF009 OK | heuristic | completed ([details](test_question_WF009.md)) |
| WF010 | Which workflows are failing most often? | WF010 OK | heuristic | completed ([details](test_question_WF010.md)) |

## 2. Scenarios (edge cases, clarifications, errors)

| Scenario | Turns | Result of last turn |
|---|---|---|
| [01_wf001_restock](01_wf001_restock.md) | 1 | completed |
| [02_wf001_custom_threshold](02_wf001_custom_threshold.md) | 1 | completed |
| [03_wf002_price_validation](03_wf002_price_validation.md) | 1 | completed |
| [04_wf003_vendor_csv](04_wf003_vendor_csv.md) | 1 | completed |
| [05_wf003_vendor_xlsx](05_wf003_vendor_xlsx.md) | 1 | completed |
| [06_wf004_seo_sample_product_missing_info](06_wf004_seo_sample_product_missing_info.md) | 1 | completed |
| [07_wf004_seo_complete_product](07_wf004_seo_complete_product.md) | 1 | completed |
| [08_wf005_order_found](08_wf005_order_found.md) | 1 | completed |
| [09_wf005_not_found_then_corrected](09_wf005_not_found_then_corrected.md) | 2 | needs_input -> completed |
| [10_wf005_shipment_api_retry](10_wf005_shipment_api_retry.md) | 1 | completed |
| [11_wf005_shipment_api_down_degrades_gracefully](11_wf005_shipment_api_down_degrades_gracefully.md) | 1 | completed |
| [12_wf005_by_customer_email](12_wf005_by_customer_email.md) | 1 | completed |
| [13_wf006_duplicates](13_wf006_duplicates.md) | 1 | completed |
| [14_wf007_asks_for_missing_goal_and_dates_then_generates](14_wf007_asks_for_missing_goal_and_dates_then_generates.md) | 2 | needs_input -> completed |
| [15_wf008_keywords_sample_file](15_wf008_keywords_sample_file.md) | 1 | completed |
| [16_wf008_keywords_inline](16_wf008_keywords_inline.md) | 1 | completed |
| [17_wf009_assign_urgent_task](17_wf009_assign_urgent_task.md) | 1 | completed |
| [18_wf009_no_suitable_employee_escalates](18_wf009_no_suitable_employee_escalates.md) | 1 | completed |
| [19_wf010_failing_workflows](19_wf010_failing_workflows.md) | 1 | completed |
| [20_wf010_agents_own_live_logs](20_wf010_agents_own_live_logs.md) | 1 | completed |
| [21_out_of_scope_request](21_out_of_scope_request.md) | 1 | no_match |
| [22_ambiguous_request_asks_which_workflow](22_ambiguous_request_asks_which_workflow.md) | 2 | ambiguous -> completed |
