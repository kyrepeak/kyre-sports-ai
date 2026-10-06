from devsystem.wnba_pushstate_repair_v1_step1_root_cause_cert import diagnose


def test_step1_identifies_single_pushstate_loop_owner_without_product_patch():
    report = diagnose()

    assert report["step"] == "1/4"
    assert report["scope"] == "root_cause_diagnosis_only"
    assert report["owner"] == "_pin_deep_wnba_shell_route"
    assert report["owner_file"] == "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
    assert report["unconditional_shell_query_writes"] is True
    assert report["render_time_pin"] is True
    assert report["wrapped_navigation_query_writer"] is True
    assert report["frozen_navigation_writer_present"] is True
    assert report["feedback_loop_proven"] is True
    assert report["product_runtime_patch_in_step1"] is False
