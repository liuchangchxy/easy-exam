import os
import shutil
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Ensure automation/sidecar is on sys.path for direct or discovered execution
_sidecar_dir = Path(__file__).resolve().parent
if str(_sidecar_dir) not in sys.path:
    sys.path.insert(0, str(_sidecar_dir))

import dispatcher


class DispatchReceiptTests(unittest.TestCase):
    def test_recovery_pr_identity_uses_only_canonical_rest_author(self):
        # 1. Canonical Bot PASS
        bot_rest = {"user": {"login": "chang-implementer[bot]", "type": "Bot"}}
        self.assertTrue(dispatcher.is_valid_canonical_pr_author(bot_rest))

        # 2. Human FAIL
        human_rest = {"user": {"login": "liuchangchxy", "type": "User"}}
        self.assertFalse(dispatcher.is_valid_canonical_pr_author(human_rest))

        # 3. Unrelated bot FAIL
        unrelated_bot_rest = {"user": {"login": "other-implementer[bot]", "type": "Bot"}}
        self.assertFalse(dispatcher.is_valid_canonical_pr_author(unrelated_bot_rest))

        # 4. Aux App representation does not override canonical PASS
        app_slug_display = {
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
            "author_display": "app/chang-implementer",
        }
        self.assertTrue(dispatcher.is_valid_canonical_pr_author(app_slug_display))

        wrong_rest_with_matching_display = {
            "user": {"login": "other-implementer[bot]", "type": "Bot"},
            "author_display": "app/chang-implementer",
        }
        self.assertFalse(dispatcher.is_valid_canonical_pr_author(wrong_rest_with_matching_display))

        # 5. Missing canonical fields FAIL CLOSED
        self.assertFalse(dispatcher.is_valid_canonical_pr_author(None))
        self.assertFalse(dispatcher.is_valid_canonical_pr_author({}))
        self.assertFalse(dispatcher.is_valid_canonical_pr_author({"user": None}))
        self.assertFalse(dispatcher.is_valid_canonical_pr_author({"user": {}}))
        self.assertFalse(dispatcher.is_valid_canonical_pr_author({"user": {"login": "chang-implementer[bot]"}}))
        self.assertFalse(dispatcher.is_valid_canonical_pr_author({"user": {"type": "Bot"}}))

    def test_extracts_real_conversation_id_from_agentapi_response(self):
        self.assertEqual(
            dispatcher.extract_conversation_id(
                '{"newConversation":{"conversationId":"156b2de3-09be-47f0-863b-2080b298a57e"}}'
            ),
            "156b2de3-09be-47f0-863b-2080b298a57e",
        )

    def test_rejects_success_output_without_conversation_id(self):
        self.assertIsNone(dispatcher.extract_conversation_id('{"response":{"accepted":true}}'))
        self.assertIsNone(dispatcher.extract_conversation_id('not-json'))

    @patch.object(dispatcher, "append_dispatch_audit", create=True)
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", create=True)
    @patch.object(dispatcher, "dispatch_agent", create=True)
    def test_confirmed_launch_writes_receipt_without_fail_closed(self, launch, fail_closed, audit):
        launch.return_value = {
            "launch_confirmed": True,
            "conversation_id": "156b2de3-09be-47f0-863b-2080b298a57e",
            "agentapi_invoked": True,
            "exit_code": 0,
            "timeout": False,
            "installation_id": 42,
            "token_expires_at": "2030-01-01T00:00:00Z",
            "error_category": None,
        }
        record = dispatcher.process_claimed_dispatch(
            "liuchangchxy/easy-exam", 9, "Validation", "changes-requested", "attempt-1"
        )
        self.assertTrue(record["launch_confirmed"])
        self.assertEqual(record["final_coordination_state"], "agent-working")
        self.assertEqual(record["conversation_id"], "156b2de3-09be-47f0-863b-2080b298a57e")
        self.assertEqual(record["installation_id"], 42)
        self.assertEqual(record["token_expires_at"], "2030-01-01T00:00:00Z")
        fail_closed.assert_not_called()
        audit.assert_called()

    @patch.object(dispatcher, "append_dispatch_audit", create=True)
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", create=True)
    @patch.object(dispatcher, "dispatch_agent", create=True)
    def test_token_setup_failure_fails_closed(self, launch, fail_closed, audit):
        launch.return_value = {
            "launch_confirmed": False,
            "conversation_id": None,
            "agentapi_invoked": False,
            "exit_code": None,
            "timeout": False,
            "error_category": "credential_setup_exception",
        }
        record = dispatcher.process_claimed_dispatch(
            "liuchangchxy/easy-exam", 9, "Validation", "changes-requested", "attempt-2"
        )
        self.assertEqual(record["final_coordination_state"], "infra-blocked")
        fail_closed.assert_called_once()
        audit.assert_called()

    @patch.object(dispatcher, "build_implementer_environment", side_effect=RuntimeError("private detail"))
    @patch.object(dispatcher, "get_agentapi_cmd_prefix", return_value=["agentapi"])
    def test_environment_exception_never_invokes_agentapi(self, prefix, credentials):
        result = dispatcher.dispatch_agent("owner/repo", ".", 9, "title", "changes-requested")
        self.assertFalse(result["agentapi_invoked"])
        self.assertEqual(result["error_category"], "credential_setup_exception")

    @patch.object(dispatcher, "run_cmd", return_value=(-1, "", "", True))
    @patch.object(dispatcher, "build_implementer_environment", return_value=({}, {"expires_at": "2030-01-01T00:00:00Z", "installation_id": 42}))
    @patch.object(dispatcher, "get_agentapi_cmd_prefix", return_value=["agentapi"])
    def test_agentapi_timeout_is_not_a_confirmed_launch(self, prefix, credentials, run):
        result = dispatcher.dispatch_agent("owner/repo", ".", 9, "title", "changes-requested")
        self.assertTrue(result["agentapi_invoked"])
        self.assertTrue(result["timeout"])
        self.assertFalse(result["launch_confirmed"])
        self.assertEqual(result["error_category"], "agentapi_timeout")

    @patch.object(dispatcher, "run_cmd", return_value=(7, "", "", False))
    @patch.object(dispatcher, "build_implementer_environment", return_value=({}, {"expires_at": "2030-01-01T00:00:00Z", "installation_id": 42}))
    @patch.object(dispatcher, "get_agentapi_cmd_prefix", return_value=["agentapi"])
    def test_agentapi_nonzero_exit_is_not_a_confirmed_launch(self, prefix, credentials, run):
        result = dispatcher.dispatch_agent("owner/repo", ".", 9, "title", "changes-requested")
        self.assertEqual(result["exit_code"], 7)
        self.assertFalse(result["launch_confirmed"])
        self.assertEqual(result["error_category"], "agentapi_nonzero_exit")

    @patch.object(dispatcher, "run_cmd", return_value=(0, '{"response":{"accepted":true}}', "", False))
    @patch.object(dispatcher, "build_implementer_environment", return_value=({}, {"expires_at": "2030-01-01T00:00:00Z", "installation_id": 42}))
    @patch.object(dispatcher, "get_agentapi_cmd_prefix", return_value=["agentapi"])
    def test_success_without_id_is_not_a_confirmed_launch(self, prefix, credentials, run):
        result = dispatcher.dispatch_agent("owner/repo", ".", 9, "title", "changes-requested")
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["launch_confirmed"])
        self.assertEqual(result["error_category"], "conversation_id_missing")

    @patch.object(dispatcher, "append_dispatch_audit")
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=False)
    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": False, "error_category": "agentapi_timeout"})
    def test_failed_github_block_transition_remains_pending_for_reconciliation(self, launch, fail_closed, audit):
        record = dispatcher.process_claimed_dispatch(
            "liuchangchxy/easy-exam", 9, "Validation", "changes-requested", "attempt-4"
        )
        self.assertEqual(record["event"], "fail_closed_pending")
        self.assertEqual(record["final_coordination_state"], "agent-working")
        self.assertEqual(record["error_category"], "fail_closed_github_update_failed")
        fail_closed.assert_called_once()
        self.assertGreaterEqual(audit.call_count, 2)

    @patch.object(dispatcher, "set_issue_labels")
    @patch.object(dispatcher, "append_dispatch_audit")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "changes-requested"}, {"name": "frozen-spec"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 9, "title": "Validation", "labels": [{"name": "changes-requested"}, {"name": "frozen-spec"}]}])
    def test_dry_run_does_not_claim_or_dispatch(self, issues, details, audit, transition):
        old_dry_run = dispatcher.EASYEXAM_DRY_RUN
        dispatcher.EASYEXAM_DRY_RUN = True
        try:
            with patch.object(dispatcher, "dispatch_agent") as launch:
                dispatcher.poll_cycle()
            transition.assert_not_called()
            launch.assert_not_called()
            audit.assert_not_called()
        finally:
            dispatcher.EASYEXAM_DRY_RUN = old_dry_run

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_restart_reconciliation_fails_closed_incomplete_claim(self, fail_closed, details):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "dispatch_audit.jsonl"
            audit_path.write_text(json.dumps({
                "attempt_id": "interrupted",
                "event": "claimed",
                "repo": "liuchangchxy/easy-exam",
                "issue_number": 9,
                "source_label": "changes-requested",
                "claim_result": True,
            }) + "\n", encoding="utf-8")
            with patch.object(dispatcher, "DISPATCH_AUDIT_PATH", audit_path):
                self.assertTrue(dispatcher.reconcile_incomplete_dispatches("liuchangchxy/easy-exam"))
            fail_closed.assert_called_once()
            rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[-1]["event"], "finalized")
            self.assertEqual(rows[-1]["final_coordination_state"], "infra-blocked")

    @patch.object(dispatcher, "append_dispatch_audit", create=True)
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", create=True)
    @patch.object(dispatcher, "dispatch_agent", side_effect=RuntimeError("sensitive detail"), create=True)
    def test_unexpected_exception_fails_closed_without_echoing_exception(self, launch, fail_closed, audit):
        record = dispatcher.process_claimed_dispatch(
            "liuchangchxy/easy-exam", 9, "Validation", "changes-requested", "attempt-3"
        )
        self.assertEqual(record["error_category"], "unexpected_dispatch_exception")
        self.assertNotIn("sensitive detail", str(record))
        self.assertEqual(record["final_coordination_state"], "infra-blocked")
        fail_closed.assert_called_once()
        audit.assert_called()

    def test_audit_append_is_jsonl_and_has_no_secret_fields(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "dispatch_audit.jsonl"
            with patch.object(dispatcher, "DISPATCH_AUDIT_PATH", audit_path, create=True):
                dispatcher.append_dispatch_audit({"attempt_id": "a", "GH_TOKEN": "must-not-be-written"})
                line = audit_path.read_text(encoding="utf-8").strip()
                self.assertIn('"attempt_id": "a"', line)
                self.assertNotIn("must-not-be-written", line)
                self.assertNotIn('"GH_TOKEN"', line)

    def test_implementer_prompt_forbids_plain_write_and_specifies_wrappers(self):
        prompt = dispatcher.build_implementer_prompt("liuchangchxy/easy-exam", ".", 9, "Test", "changes-requested")
        self.assertIn("严禁使用普通 git push", prompt)
        self.assertIn("严禁使用普通 gh pr create", prompt)
        self.assertIn("NEVER use ordinary gh for writes", prompt)
        self.assertIn("NEVER use ordinary git push", prompt)
        self.assertIn("use app-gh", prompt)
        self.assertIn("use app-git-push", prompt)
        self.assertIn("mechanically blocked", prompt)
        self.assertIn("app-git-push", prompt)
        self.assertIn("app-gh", prompt)
        self.assertIn(str(dispatcher.APP_GIT_PUSH_EXECUTOR), prompt)
        self.assertIn(str(dispatcher.APP_GH_EXECUTOR), prompt)

    def test_launch_does_not_inject_tokens_into_caller_env(self):
        with patch.dict(os.environ, {"GH_TOKEN": "leak_candidate", "GITHUB_APP_TOKEN": "leak2"}):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("importlib.util.spec_from_file_location") as mock_spec:
                    mock_spec.return_value.loader = MagicMock()
                    child_env, metadata = dispatcher.build_implementer_environment("liuchangchxy/easy-exam")
                    self.assertNotIn("GH_TOKEN", child_env)
                    self.assertNotIn("GITHUB_APP_TOKEN", child_env)
                    self.assertIsNone(metadata.get("expires_at"))

    def test_fail_closed_guard_ensures_repo_push_url_and_hook(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory) / ".git"
            git_dir.mkdir()
            with patch("dispatcher.run_cmd") as mock_run:
                dispatcher.ensure_workspace_fail_closed_guard(directory)
                hook = git_dir / "hooks" / "pre-push"
                self.assertTrue(hook.exists())
                self.assertIn("FAIL-CLOSED", hook.read_text(encoding="utf-8"))
                self.assertTrue(any("FAIL_CLOSED_DIRECT_PUSH_DISABLED" in str(c) for c in mock_run.call_args_list))


    def test_normal_issue_prompt_unchanged(self):
        prompt = dispatcher.build_implementer_prompt("liuchangchxy/easy-exam", ".", 9, "Normal Task", "agent-ready")
        self.assertNotIn("4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertNotIn("agent/issue-4-self-contained-mobile-e2e-bot", prompt)
        self.assertNotIn("THIS IS A RECOVERY TASK", prompt)
        self.assertNotIn("MODE: RECOVERY", prompt)
        self.assertEqual(dispatcher.get_dispatch_mode(9), "normal")
        self.assertIsNone(dispatcher.get_recovery_spec(9))

    def test_issue_4_recovery_mode_mandatory_spec_and_constraints(self):
        prompt = dispatcher.build_implementer_prompt("liuchangchxy/easy-exam", ".", 4, "Infrastructure Phase 3A: Make Mobile Interaction E2E self-contained", "agent-ready")
        self.assertEqual(dispatcher.get_dispatch_mode(4), "recovery")
        self.assertIn("THIS IS A RECOVERY TASK", prompt)
        self.assertIn("4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertIn("agent/issue-4-self-contained-mobile-e2e-bot", prompt)
        self.assertIn("frontend/tests/mobile_interaction_suite.mjs", prompt)
        self.assertIn("frontend/tests/fixtures/mobile_interaction_questions.md", prompt)
        self.assertIn("app-git-push", prompt)
        self.assertIn("app-gh", prompt)
        self.assertIn("Do not create any new implementation commit", prompt)
        self.assertIn("GET /repos/liuchangchxy/easy-exam/pulls/<PR_NUMBER>", prompt)
        self.assertIn("pull_request.user.login == chang-implementer[bot]", prompt)
        self.assertIn("pull_request.user.type == Bot", prompt)
        self.assertIn("app/chang-implementer", prompt)
        self.assertIn("不能覆盖或替代 REST canonical author 字段", prompt)

    def test_issue_4_recovery_prompt_mandates_exact_sha_reuse(self):
        prompt = dispatcher.build_implementer_prompt("liuchangchxy/easy-exam", ".", 4, "Infrastructure Phase 3A", "agent-ready")
        self.assertIn("Preserved implementation SHA: 4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertIn("git rev-parse 4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertIn("git cat-file -e 4428ef14bffd0bf94fc28bff508e7be5ec2a30f0^{commit}", prompt)
        self.assertIn("git checkout -B agent/issue-4-self-contained-mobile-e2e-bot 4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertIn("HEAD 必须是 4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertIn("--expected-sha 4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)

    def test_issue_4_recovery_prompt_contains_failure_stop_conditions(self):
        prompt = dispatcher.build_implementer_prompt("liuchangchxy/easy-exam", ".", 4, "Infrastructure Phase 3A", "agent-ready")
        self.assertIn("若出现以下任一情况，必须立即 STOP 并输出 BLOCKER 报告", prompt)
        self.assertIn("preserved SHA 不存在", prompt)
        self.assertIn("preserved diff 不符合两文件限制", prompt)
        self.assertIn("branch head 不是 preserved SHA", prompt)
        self.assertIn("branch 已存在但 SHA 冲突", prompt)
        self.assertIn("app-git-push 失败", prompt)
        self.assertIn("remote SHA mismatch", prompt)
        self.assertIn("app-gh 失败", prompt)
        self.assertIn("REST canonical PR author 无效", prompt)
        self.assertIn("需要修改实现代码才能继续", prompt)

    def test_issue_4_recovery_prompt_forbids_reimplementation_and_product_mutation(self):
        prompt = dispatcher.build_implementer_prompt("liuchangchxy/easy-exam", ".", 4, "Infrastructure Phase 3A", "agent-ready")
        self.assertIn("No Reimplementation", prompt)
        self.assertIn("严禁重新实现任何业务逻辑或测试逻辑", prompt)
        self.assertIn("不修改上述允许文件", prompt)
        self.assertIn("不重新编辑 fixture", prompt)
        self.assertIn("不重新编辑 suite", prompt)
        self.assertIn("绝对不触碰 EasyExam 产品代码", prompt)
        self.assertIn("严禁自行修改代码或重新实现", prompt)

    def test_render_dispatch_prompt_shares_exact_builder_with_dispatch(self):
        preview = dispatcher.render_dispatch_prompt(4)
        production = dispatcher.build_implementer_prompt(
            dispatcher.EASYEXAM_REPO, dispatcher.EASYEXAM_REPO_PATH, 4, "Issue #4", "agent-ready"
        )
        self.assertEqual(preview, production)

    def test_issue_4_changes_requested_repair_prompt(self):
        prompt = dispatcher.build_implementer_prompt(
            "liuchangchxy/easy-exam", ".", 4, "Infrastructure Phase 3A", "changes-requested"
        )
        # 1. Target bindings
        self.assertIn("PR #15", prompt)
        self.assertIn("agent/issue-4-self-contained-mobile-e2e-bot", prompt)
        self.assertIn("4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", prompt)
        self.assertIn("REQUEST_CHANGES", prompt)

        # 2. Repair scope & allowed file
        self.assertIn("CHROME_PATH", prompt)
        self.assertIn("frontend/tests/mobile_interaction_suite.mjs", prompt)

        # 3. Forbids other files
        self.assertIn("严禁修改任何其它文件", prompt)
        self.assertIn("严禁修改 fixture 题目", prompt)
        self.assertIn("严禁修改 EasyExam 产品代码", prompt)
        self.assertNotIn("app-gh pr create", prompt)

        # 4. Allows new repair commit & controlled push
        self.assertIn("app-git-push", prompt)
        self.assertIn("app-gh", prompt)
        self.assertIn("允许创建一个新的 repair commit", prompt)
        self.assertIn("--expected-sha <NEW_REPAIR_SHA>", prompt)

    def test_render_dispatch_prompt_shares_exact_builder_with_dispatch_changes_requested(self):
        preview = dispatcher.render_dispatch_prompt(4, source_label="changes-requested")
        production = dispatcher.build_implementer_prompt(
            dispatcher.EASYEXAM_REPO, dispatcher.EASYEXAM_REPO_PATH, 4, "Issue #4", "changes-requested"
        )
        self.assertEqual(preview, production)

    def test_normal_flows_unaffected(self):
        # 1. Normal agent-ready
        normal_ready = dispatcher.build_implementer_prompt(
            "liuchangchxy/easy-exam", ".", 9, "Normal", "agent-ready"
        )
        self.assertIn("本次触发来源为 agent-ready", normal_ready)
        self.assertNotIn("4428ef14bffd0bf94fc28bff508e7be5ec2a30f0", normal_ready)

        # 2. Normal recovery mode (Issue 4 agent-ready)
        recovery_prompt = dispatcher.build_implementer_prompt(
            "liuchangchxy/easy-exam", ".", 4, "Recovery", "agent-ready"
        )
        self.assertIn("THIS IS A RECOVERY TASK", recovery_prompt)
        self.assertIn("Do not create any new implementation commit", recovery_prompt)

        # 3. Ordinary changes-requested for other issues
        other_cr = dispatcher.build_implementer_prompt(
            "liuchangchxy/easy-exam", ".", 9, "Other", "changes-requested"
        )
        self.assertIn("本次触发来源为 changes-requested", other_cr)
        self.assertNotIn("PR #15", other_cr)
        self.assertNotIn("CHROME_PATH", other_cr)

    def test_recovery_spec_is_trusted_and_isolated_from_caller_env(self):
        with patch.dict(os.environ, {"PRESERVED_SHA": "hacked", "RECOVERY_BRANCH": "hacked"}):
            spec = dispatcher.get_recovery_spec(4)
            self.assertIsNotNone(spec)
            self.assertEqual(spec.preserved_sha, "4428ef14bffd0bf94fc28bff508e7be5ec2a30f0")
            self.assertEqual(spec.recovery_branch, "agent/issue-4-self-contained-mobile-e2e-bot")
            self.assertEqual(
                spec.allowed_changed_files,
                [
                    "frontend/tests/mobile_interaction_suite.mjs",
                    "frontend/tests/fixtures/mobile_interaction_questions.md",
                ],
            )
            self.assertFalse(spec.allow_reimplementation)
            self.assertFalse(spec.allow_new_implementation_commit)


class CoordinationRoutingAndBypassTests(unittest.TestCase):
    def setUp(self):
        dispatcher.CLAIM_BACKOFF_MAP.clear()

    @patch.object(dispatcher, "execute_coordination_write", return_value=(0, "", "", False))
    @patch.object(dispatcher, "get_issue_details")
    def test_cas_transition_changes_requested_to_agent_working_success(self, mock_details, mock_write):
        # Pre-read returns changes-requested; post-read returns agent-working
        mock_details.side_effect = [
            {"state": "OPEN", "labels": [{"name": "changes-requested"}, {"name": "frozen-spec"}]},
            {"state": "OPEN", "labels": [{"name": "agent-working"}, {"name": "frozen-spec"}]},
        ]
        ok, reason = dispatcher.cas_transition_coordination_state(
            "liuchangchxy/easy-exam", 4, "changes-requested", "agent-working"
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "transition_succeeded")
        mock_write.assert_called_once()
        write_args = mock_write.call_args[0][0]
        self.assertIn("--remove-label", write_args)
        self.assertIn("changes-requested", write_args)
        self.assertIn("--add-label", write_args)
        self.assertIn("agent-working", write_args)

    @patch.object(dispatcher, "execute_coordination_write")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "agent-ready"}, {"name": "frozen-spec"}]})
    def test_cas_transition_fails_closed_on_stale_expected_state(self, mock_details, mock_write):
        # Expected changes-requested, but issue has agent-ready
        ok, reason = dispatcher.cas_transition_coordination_state(
            "liuchangchxy/easy-exam", 4, "changes-requested", "agent-working"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "stale_expected_state")
        mock_write.assert_not_called()

    @patch.object(dispatcher, "execute_coordination_write")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "agent-working"}, {"name": "frozen-spec"}]})
    def test_cas_transition_fails_closed_if_target_already_present(self, mock_details, mock_write):
        # Target agent-working is already present
        ok, reason = dispatcher.cas_transition_coordination_state(
            "liuchangchxy/easy-exam", 4, "changes-requested", "agent-working"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "target_already_present")
        mock_write.assert_not_called()

    @patch.object(dispatcher, "execute_coordination_write")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "changes-requested"}, {"name": "infra-blocked"}]})
    def test_cas_transition_fails_closed_if_infra_blocked_present(self, mock_details, mock_write):
        # Issue has infra-blocked label, cannot be claimed
        ok, reason = dispatcher.cas_transition_coordination_state(
            "liuchangchxy/easy-exam", 4, "changes-requested", "agent-working"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "blocking_label_present")
        mock_write.assert_not_called()

    @patch.object(dispatcher, "execute_coordination_write", return_value=(1, "", "write error", False))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "changes-requested"}, {"name": "frozen-spec"}]})
    def test_github_write_failure_preserves_state_and_reports_error(self, mock_details, mock_write):
        ok, reason = dispatcher.cas_transition_coordination_state(
            "liuchangchxy/easy-exam", 4, "changes-requested", "agent-working"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "github_write_failed")

    def test_claim_failure_records_backoff_and_blocks_storm(self):
        # First failure
        d1 = dispatcher.record_claim_failure(4, "github_write_failed", base_backoff=10.0)
        self.assertEqual(d1, 10.0)
        in_backoff, rem1 = dispatcher.is_in_claim_backoff(4)
        self.assertTrue(in_backoff)
        self.assertGreater(rem1, 0.0)

        # Second failure doubles backoff (exponential)
        d2 = dispatcher.record_claim_failure(4, "github_write_failed", base_backoff=10.0)
        self.assertEqual(d2, 20.0)

        # Third failure quadruples backoff
        d3 = dispatcher.record_claim_failure(4, "github_write_failed", base_backoff=10.0)
        self.assertEqual(d3, 40.0)

        # Reset clears backoff
        dispatcher.reset_claim_backoff(4)
        in_backoff_after, _ = dispatcher.is_in_claim_backoff(4)
        self.assertFalse(in_backoff_after)

    def test_duplicate_sidecar_mutex_blocks_concurrent_instance(self):
        lock1 = dispatcher.WindowsSingleInstanceLock("Local\\TestEasyExamDuplicateSidecarMutex")
        self.assertTrue(lock1.acquire())
        try:
            lock2 = dispatcher.WindowsSingleInstanceLock("Local\\TestEasyExamDuplicateSidecarMutex")
            self.assertFalse(lock2.acquire(), "Second instance must be rejected by mutex")
        finally:
            lock1.release()

    def test_absolute_gh_exe_bypasses_gh_cmd_guard(self):
        """
        Regression test documenting that PATH shim (gh.cmd) does NOT protect against
        direct absolute invocation of C:\\Program Files\\GitHub CLI\\gh.exe.
        """
        import subprocess
        gh_cmd = "gh.cmd" if sys.platform == "win32" and shutil.which("gh.cmd") else "gh"
        proc_shim = subprocess.run(
            [gh_cmd, "issue", "edit", "--help"],
            capture_output=True,
            text=True,
            shell=True,
        )
        self.assertEqual(proc_shim.returncode, 1)
        self.assertIn("GitHub write blocked in Implementer shell", proc_shim.stderr)

        # 2. Direct absolute path invocation runs real gh.exe without hitting gh_guard.py
        real_gh = r"C:\Program Files\GitHub CLI\gh.exe"
        if os.path.isfile(real_gh):
            proc_real = subprocess.run(
                [real_gh, "issue", "edit", "--help"],
                capture_output=True,
                text=True,
                shell=False,
            )
            # Exits 0 and prints usage, proving gh_guard.py was bypassed
            self.assertEqual(proc_real.returncode, 0)
            self.assertIn("Edit one or more issues", proc_real.stdout)
            self.assertNotIn("GitHub write blocked in Implementer shell", proc_real.stderr)

    def test_absolute_git_exe_bypasses_git_cmd_guard(self):
        """
        Regression test documenting that PATH shim (git.cmd) does NOT protect against
        direct absolute invocation of D:\\Program Files\\Git\\cmd\\git.exe.
        """
        import subprocess
        # 1. PATH invocation 'git' hits guard and blocks 'push -h'
        git_cmd = "git.cmd" if sys.platform == "win32" and shutil.which("git.cmd") else "git"
        proc_shim = subprocess.run(
            [git_cmd, "push", "-h"],
            capture_output=True,
            text=True,
            shell=True,
        )
        self.assertEqual(proc_shim.returncode, 1)
        self.assertIn("Direct git push blocked in Implementer shell", proc_shim.stderr)

        # 2. Direct absolute path invocation runs real git.exe without hitting git_guard.py
        real_git = r"D:\Program Files\Git\cmd\git.exe"
        if os.path.isfile(real_git):
            proc_real = subprocess.run(
                [real_git, "push", "-h"],
                capture_output=True,
                text=True,
                shell=False,
            )
            # Exits 1 (due to -h usage exit) and prints git push usage, proving git_guard.py was bypassed
            self.assertIn("usage: git push", proc_real.stderr + proc_real.stdout)
            self.assertNotIn("Direct git push blocked in Implementer shell", proc_real.stderr)


if __name__ == "__main__":
    unittest.main()

