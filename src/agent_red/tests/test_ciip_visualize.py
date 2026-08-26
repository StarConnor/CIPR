from agent_red.analysis.ciip_visualize import CIIPViz, load_records


def _record(task: str, prompt_expression: str, skills: str, attack: str, task_s: str, alert: str, read: str = "failure"):
    return {
        "task": task,
        "prompt_expression": prompt_expression,
        "skills": skills,
        "attack_success": attack,
        "task_success": task_s,
        "alert_success": alert,
        "read_injected_file": read,
    }


def test_compare_builds_task_prompt_skill_matrix():
    viz = CIIPViz(
        [
            _record("prepare_env", "direct", "none", "success", "failure", "failure"),
            _record("prepare_env", "direct", "none", "failure", "success", "failure"),
            _record("prepare_env", "baseline", "skills_a", "success", "success", "success"),
            _record("run_task", "direct", "none", "failure", "failure", "failure"),
        ]
    )

    table = viz.compare("asr")

    assert table.row_fields == ("task", "prompt_expression")
    assert table.cols == ["none", "skills_a"]
    assert table.values[("prepare_env", "baseline")]["skills_a"] == 1.0
    assert table.values[("prepare_env", "direct")]["none"] == 0.5
    assert table.values[("run_task", "direct")]["none"] == 0.0


def test_compare_task_only_ignores_other_axes():
    viz = CIIPViz(
        [
            _record("prepare_env", "direct", "none", "success", "failure", "failure"),
            _record("prepare_env", "baseline", "skills_a", "failure", "success", "failure"),
            _record("run_task", "direct", "none", "failure", "failure", "failure"),
        ]
    )

    table = viz.compare("asr", rows=("task",), cols=None)

    assert table.col_field is None
    assert table.values[("prepare_env",)]["__all__"] == 0.5
    assert table.values[("run_task",)]["__all__"] == 0.0


def test_to_latex_is_copyable_plain_text():
    viz = CIIPViz([_record("prepare_env", "direct", "none", "success", "failure", "failure")])
    table = viz.compare("asr")

    latex = table.to_latex()

    assert "\\begin{tabular}" in latex
    assert "prepare\\_env" in latex
    assert "0.000" not in latex


def test_load_records_handles_list_and_result_payload(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(
        """
        [
          {
            "sample": {"id": "1", "task": "prepare_env", "metadata": {"prompt_expression": {"name": "Direct"}, "skills": {"mode": "none"}}},
            "result": {"attack_success": "success", "task_success": "failure", "alert_success": "failure", "read_injected_file": "success"}
          }
        ]
        """,
        encoding="utf-8",
    )

    records = load_records(path)

    assert len(records) == 1
    assert records[0]["task"] == "prepare_env"
    assert records[0]["prompt_expression"] == "Direct"
    assert records[0]["skills"] == "none"
    assert records[0]["attack_success"] == 1.0
    assert records[0]["read_injected_file"] == 1.0


def test_compare_supports_read_injected_file_metric_and_condition():
    viz = CIIPViz(
        [
            _record("prepare_env", "direct", "none", "success", "failure", "failure", "success"),
            _record("prepare_env", "direct", "none", "failure", "success", "failure", "success"),
            _record("prepare_env", "direct", "none", "success", "success", "success", "failure"),
        ]
    )

    rif = viz.compare("rif", rows=("task",), cols=None)
    assert rif.metric == "read_injected_file"
    assert rif.values[("prepare_env",)]["__all__"] == 2 / 3

    conditional_asr = viz.compare("asr", rows=("task",), cols=None, where={"read_injected_file": "success"})
    assert conditional_asr.metric == "attack_success"
    assert conditional_asr.condition == {"read_injected_file": "success"}
    assert conditional_asr.metric_label == "attack_success | read_injected_file=success"
    assert conditional_asr.values[("prepare_env",)]["__all__"] == 0.5
    assert "Condition:" in conditional_asr.to_markdown()


def test_comparison_table_exports_tidy_records_for_plotting():
    viz = CIIPViz(
        [
            _record("prepare_env", "direct", "none", "success", "failure", "failure"),
            _record("prepare_env", "direct", "none", "failure", "success", "failure"),
            _record("prepare_env", "direct", "skills_a", "success", "success", "success"),
        ]
    )

    table = viz.compare("asr", rows=("task",), cols="skills")
    records = table.to_records()

    assert records == [
        {
            "task": "prepare_env",
            "metric": "attack_success",
            "metric_label": "attack_success",
            "value": 0.5,
            "matched": 1,
            "total": 2,
            "condition": "",
            "skills": "none",
        },
        {
            "task": "prepare_env",
            "metric": "attack_success",
            "metric_label": "attack_success",
            "value": 1.0,
            "matched": 1,
            "total": 1,
            "condition": "",
            "skills": "skills_a",
        },
    ]


def test_comparison_table_to_frame_returns_pandas_dataframe():
    viz = CIIPViz([_record("prepare_env", "direct", "none", "success", "failure", "failure")])

    df = viz.compare("asr", rows=("task",), cols=None).to_frame()

    assert list(df.columns) == ["task", "metric", "metric_label", "value", "matched", "total", "condition"]
    assert df.loc[0, "task"] == "prepare_env"
    assert df.loc[0, "value"] == 1.0
