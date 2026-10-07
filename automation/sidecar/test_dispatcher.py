import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import time
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

    @staticmethod
    def _find_real_gh_executable() -> str | None:
        for drive in ["C", "D"]:
            for sub in [r"Program Files\GitHub CLI\gh.exe", r"Program Files\GitHub CLI\bin\gh.exe"]:
                candidate = f"{drive}:\\{sub}"
                if os.path.isfile(candidate):
                    return candidate
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if not p:
                continue
            cand = os.path.join(p, "gh.exe")
            if os.path.isfile(cand):
                return cand
        return None

    @staticmethod
    def _find_real_git_executable() -> str | None:
        for drive in ["C", "D"]:
            for sub in [r"Program Files\Git\cmd\git.exe", r"Program Files\Git\bin\git.exe"]:
                candidate = f"{drive}:\\{sub}"
                if os.path.isfile(candidate):
                    return candidate
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if not p:
                continue
            cand = os.path.join(p, "git.exe")
            if os.path.isfile(cand):
                return cand
        return None

    def test_absolute_gh_exe_bypasses_gh_cmd_guard(self):
        """
        Regression test documenting that PATH shim (gh.cmd) does NOT protect against
        direct absolute invocation of gh.exe.
        Deterministic across local Windows environments and GitHub Actions runners.
        """
        if sys.platform != "win32":
            self.skipTest("PATH shim bypass regression is specific to Windows")

        import subprocess

        with tempfile.TemporaryDirectory() as td:
            # 1. Deterministic PATH shim that blocks writes
            shim_path = os.path.join(td, "gh.cmd")
            with open(shim_path, "w", encoding="utf-8") as f:
                f.write("@echo off\n>&2 echo GitHub write blocked in Implementer shell\nexit /b 1\n")

            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")

            # 1. PATH invocation hits shim and blocks
            proc_shim = subprocess.run(
                ["gh.cmd", "issue", "edit", "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                env=env,
            )
            self.assertEqual(proc_shim.returncode, 1)
            self.assertIn("GitHub write blocked in Implementer shell", proc_shim.stderr)

            # 2. Direct absolute path invocation runs real gh.exe without hitting guard
            real_gh = self._find_real_gh_executable()
            self.assertIsNotNone(real_gh, "Real gh.exe must be present on Windows runner")
            proc_real = subprocess.run(
                [real_gh, "issue", "edit", "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=env,
            )
            # Exits 0 and prints usage, proving gh_guard.py was bypassed
            self.assertEqual(proc_real.returncode, 0)
            self.assertIn("Edit one or more issues", proc_real.stdout)
            self.assertNotIn("GitHub write blocked in Implementer shell", proc_real.stderr)

    def test_absolute_git_exe_bypasses_git_cmd_guard(self):
        """
        Regression test documenting that PATH shim (git.cmd) does NOT protect against
        direct absolute invocation of git.exe.
        Deterministic across local Windows environments and GitHub Actions runners.
        """
        if sys.platform != "win32":
            self.skipTest("PATH shim bypass regression is specific to Windows")

        import subprocess

        with tempfile.TemporaryDirectory() as td:
            # 1. Deterministic PATH shim that blocks push
            shim_path = os.path.join(td, "git.cmd")
            with open(shim_path, "w", encoding="utf-8") as f:
                f.write("@echo off\n>&2 echo Direct git push blocked in Implementer shell. Use app-git-push.\nexit /b 1\n")

            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")

            # 1. PATH invocation hits shim and blocks
            proc_shim = subprocess.run(
                ["git.cmd", "push", "-h"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                env=env,
            )
            self.assertEqual(proc_shim.returncode, 1)
            self.assertIn("Direct git push blocked in Implementer shell", proc_shim.stderr)

            # 2. Direct absolute path invocation runs real git.exe without hitting guard
            real_git = self._find_real_git_executable()
            self.assertIsNotNone(real_git, "Real git.exe must be present on Windows runner")
            proc_real = subprocess.run(
                [real_git, "push", "-h"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=env,
            )
            # Exits with git usage output (returncode 129 in git CLI), proving guard was bypassed
            self.assertIn("usage: git push", proc_real.stderr + proc_real.stdout)
            self.assertNotIn("Direct git push blocked in Implementer shell", proc_real.stderr)


class ClosureV1DeterministicAcceptanceTests(unittest.TestCase):
    """
    Deterministic acceptance suite for Automation Closure v1 matching Issue #35 Section 20:
    - ownership / lease
    - two-worker claim race
    - duplicate events
    - duplicate failed checks
    - duplicate Review
    - repair budget
    - no repair #4
    - crash before/after launch confirmation
    - incomplete receipt
    - restart reconciliation
    - PR adoption
    - stale SHA fencing
    - failure classification
    - cancellation fencing
    - regression of existing dispatch/review/CI/auto-merge contracts
    """

    def setUp(self):
        self.ledger = dispatcher.ExecutionLedger(":memory:")
        dispatcher.set_ledger(self.ledger)

    def tearDown(self):
        if hasattr(self, "ledger") and self.ledger:
            self.ledger.close()
        dispatcher.set_ledger(None)

    def test_ownership_and_lease_lifecycle(self):
        # 1. Acquire lease
        ok, token, reason = self.ledger.acquire_lease("liuchangchxy/easy-exam", 35, "worker-1", ttl_seconds=60)
        self.assertTrue(ok)
        self.assertIsNotNone(token)
        self.assertEqual(reason, "acquired")

        # 2. Check active lease
        lease = self.ledger.get_active_lease("liuchangchxy/easy-exam", 35)
        self.assertIsNotNone(lease)
        self.assertEqual(lease["owner_id"], "worker-1")
        self.assertEqual(lease["lease_token"], token)

        # 3. Same owner renews lease
        ok_renew, renew_token, renew_reason = self.ledger.acquire_lease("liuchangchxy/easy-exam", 35, "worker-1", ttl_seconds=120)
        self.assertTrue(ok_renew)
        self.assertEqual(renew_reason, "renewed")
        self.assertEqual(renew_token, token)

        # 4. Release lease
        rel_ok = self.ledger.release_lease(token)
        self.assertTrue(rel_ok)
        self.assertIsNone(self.ledger.get_active_lease("liuchangchxy/easy-exam", 35))

    def test_two_worker_claim_race(self):
        # Worker 1 acquires lease
        ok1, token1, reason1 = self.ledger.acquire_lease("liuchangchxy/easy-exam", 35, "worker-1")
        self.assertTrue(ok1)

        # Worker 2 attempts to acquire lease for the same issue
        ok2, token2, reason2 = self.ledger.acquire_lease("liuchangchxy/easy-exam", 35, "worker-2")
        self.assertFalse(ok2, "Second worker must lose lease race")
        self.assertIsNone(token2)
        self.assertEqual(reason2, "lease_held_by_other_worker")

    def test_duplicate_events_and_idempotency_key(self):
        key = dispatcher.compute_repair_key("liuchangchxy/easy-exam", 15, "abc123def456")
        self.assertEqual(key, "repair:liuchangchxy/easy-exam:pr:15:head:abc123def456")

        self.assertFalse(self.ledger.is_repair_key_processed(key))
        self.ledger.record_claim_intent(
            repo="liuchangchxy/easy-exam",
            issue_number=35,
            owner_id="worker-1",
            lease_token="token-1",
            attempt_id="att-1",
            attempt_kind="ci_repair",
            trigger_key="trigger-1",
            repair_key=key,
        )
        self.assertTrue(self.ledger.is_repair_key_processed(key), "Processed repair key must be detected as duplicate")

    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "get_issue_details")
    def test_duplicate_failed_checks_deduplication(self, mock_details, mock_dispatch):
        mock_details.return_value = {"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]}
        mock_dispatch.return_value = {"launch_confirmed": True, "conversation_id": "test-uuid-1"}

        head_sha = "abcdef1234567890abcdef1234567890abcdef12"
        # First repair launch for failed check
        ok1, res1, meta1 = dispatcher.dispatch_automated_repair(
            repo="liuchangchxy/easy-exam",
            issue_number=35,
            pr_number=15,
            current_pr_head_sha=head_sha,
            expected_repair_baseline_sha=head_sha,
            repair_kind="ci_repair",
            cause_type="ci_failure",
            cause_id="run-1",
            failure_detail={"name": "Backend & Packaging Tests", "conclusion": "failure"},
            ledger=self.ledger,
        )
        self.assertTrue(ok1)
        self.assertEqual(res1, "repair_launched")

        # Second duplicate failed check event for same head SHA
        ok2, res2, meta2 = dispatcher.dispatch_automated_repair(
            repo="liuchangchxy/easy-exam",
            issue_number=35,
            pr_number=15,
            current_pr_head_sha=head_sha,
            expected_repair_baseline_sha=head_sha,
            repair_kind="ci_repair",
            cause_type="ci_failure",
            cause_id="run-1-duplicate",
            failure_detail={"name": "Backend & Packaging Tests", "conclusion": "failure"},
            ledger=self.ledger,
        )
        self.assertFalse(ok2, "Duplicate failed check must be ignored")
        self.assertEqual(res2, "duplicate_repair_ignored")

    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "transition_succeeded"))
    @patch.object(dispatcher, "get_issue_details")
    def test_duplicate_review_deduplication(self, mock_details, mock_cas, mock_dispatch):
        mock_details.return_value = {"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}
        mock_dispatch.return_value = {"launch_confirmed": True, "conversation_id": "test-uuid-2"}

        rejected_sha = "9999888877776666555544443333222211110000"
        ok1, res1, _ = dispatcher.dispatch_automated_repair(
            repo="liuchangchxy/easy-exam",
            issue_number=35,
            pr_number=15,
            current_pr_head_sha=rejected_sha,
            expected_repair_baseline_sha=rejected_sha,
            repair_kind="reviewer_repair",
            cause_type="reviewer_request_changes",
            cause_id="review-1",
            ledger=self.ledger,
        )
        self.assertTrue(ok1)
        self.assertEqual(res1, "repair_launched")

        # Second duplicate review event for same rejected SHA
        ok2, res2, _ = dispatcher.dispatch_automated_repair(
            repo="liuchangchxy/easy-exam",
            issue_number=35,
            pr_number=15,
            current_pr_head_sha=rejected_sha,
            expected_repair_baseline_sha=rejected_sha,
            repair_kind="reviewer_repair",
            cause_type="reviewer_request_changes",
            cause_id="review-1-replay",
            ledger=self.ledger,
        )
        self.assertFalse(ok2)
        self.assertEqual(res2, "duplicate_repair_ignored")

    @patch.object(dispatcher, "fail_closed_to_needs_human", return_value=True)
    def test_repair_budget_enforcement_and_no_repair_4(self, mock_needs_human):
        repo = "liuchangchxy/easy-exam"
        pr_number = 15

        # Record repair 1 (CI)
        can1, ord1 = self.ledger.can_attempt_repair(repo, pr_number)
        self.assertTrue(can1)
        self.assertEqual(ord1, 1)
        self.ledger.record_claim_intent(repo, 35, "w1", "tok1", "att-1", "ci_repair", "trig1", pr_number=pr_number, repair_ordinal=1)

        # Record repair 2 (Reviewer)
        can2, ord2 = self.ledger.can_attempt_repair(repo, pr_number)
        self.assertTrue(can2)
        self.assertEqual(ord2, 2)
        self.ledger.record_claim_intent(repo, 35, "w1", "tok2", "att-2", "reviewer_repair", "trig2", pr_number=pr_number, repair_ordinal=2)

        # Record repair 3 (CI)
        can3, ord3 = self.ledger.can_attempt_repair(repo, pr_number)
        self.assertTrue(can3)
        self.assertEqual(ord3, 3)
        self.ledger.record_claim_intent(repo, 35, "w1", "tok3", "att-3", "ci_repair", "trig3", pr_number=pr_number, repair_ordinal=3)

        # Attempt repair 4 -> must be strictly prohibited!
        can4, ord4 = self.ledger.can_attempt_repair(repo, pr_number)
        self.assertFalse(can4, "Repair #4 must be rejected by budget")
        self.assertEqual(ord4, 3)

        # Attempting dispatch_automated_repair on exhausted budget routes to needs-human
        with patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}]}):
            ok, res, _ = dispatcher.dispatch_automated_repair(
                repo=repo,
                issue_number=35,
                pr_number=pr_number,
                current_pr_head_sha="sha_d",
                expected_repair_baseline_sha="sha_d",
                repair_kind="ci_repair",
                cause_type="ci_failure",
                cause_id="run-4",
                failure_detail={"name": "test", "conclusion": "failure"},
                ledger=self.ledger,
            )
            self.assertFalse(ok)
            self.assertEqual(res, "repair_budget_exhausted_needs_human")
            mock_needs_human.assert_called_once()

    def test_stale_sha_fencing(self):
        # Mismatch between actual PR head and expected baseline
        self.assertTrue(dispatcher.verify_exact_head_sha("abc1234", "abc1234"))
        self.assertTrue(dispatcher.verify_exact_head_sha("ABC1234", "abc1234"))
        self.assertFalse(dispatcher.verify_exact_head_sha("abc1234", "def5678"))
        self.assertFalse(dispatcher.verify_exact_head_sha("", "abc1234"))

        with patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}]}):
            ok, res, _ = dispatcher.dispatch_automated_repair(
                repo="liuchangchxy/easy-exam",
                issue_number=35,
                pr_number=15,
                current_pr_head_sha="new_head_sha",
                expected_repair_baseline_sha="old_failed_sha",
                repair_kind="ci_repair",
                cause_type="ci_failure",
                cause_id="run-1",
                failure_detail={"name": "test", "conclusion": "failure"},
                ledger=self.ledger,
            )
            self.assertFalse(ok)
            self.assertEqual(res, "stale_head_sha_mismatch")

    def test_failure_classification(self):
        # 1. Code / test failure
        cat, _ = dispatcher.classify_ci_failure({"name": "Backend & Packaging Tests", "conclusion": "failure"})
        self.assertEqual(cat, "code_failure")

        cat, _ = dispatcher.classify_ci_failure({"output": "AssertionError: 129 != 1"})
        self.assertEqual(cat, "code_failure")

        cat, _ = dispatcher.classify_ci_failure({"message": "scan_hardcoded_paths violation detected"})
        self.assertEqual(cat, "code_failure")

        # 2. Infrastructure failure
        cat_infra, _ = dispatcher.classify_ci_failure({"output": "runner disconnected during job execution"})
        self.assertEqual(cat_infra, "infra_failure")

        cat_infra2, _ = dispatcher.classify_ci_failure({"message": "GitHub Actions outage runner timeout"})
        self.assertEqual(cat_infra2, "infra_failure")

        # 3. Ambiguous failure
        cat_amb, _ = dispatcher.classify_ci_failure({"conclusion": "cancelled"})
        self.assertEqual(cat_amb, "ambiguous")

        cat_empty, _ = dispatcher.classify_ci_failure({})
        self.assertEqual(cat_empty, "ambiguous")

    def test_cancellation_fencing(self):
        # Open & authorized
        self.assertEqual(
            dispatcher.check_cancellation_fencing({"state": "OPEN", "labels": [{"name": "frozen-spec"}]}),
            (False, "authorized"),
        )
        # Closed
        self.assertEqual(
            dispatcher.check_cancellation_fencing({"state": "CLOSED", "labels": [{"name": "frozen-spec"}]}),
            (True, "issue_not_open"),
        )
        # infra-blocked
        self.assertEqual(
            dispatcher.check_cancellation_fencing({"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "infra-blocked"}]}),
            (True, "infra_blocked"),
        )
        # needs-human
        self.assertEqual(
            dispatcher.check_cancellation_fencing({"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "needs-human"}]}),
            (True, "needs_human"),
        )
        # missing frozen-spec
        self.assertEqual(
            dispatcher.check_cancellation_fencing({"state": "OPEN", "labels": [{"name": "agent-ready"}]}),
            (True, "frozen_spec_missing"),
        )

    def test_pr_adoption_scenarios(self):
        valid_bot_pr = {
            "number": 31,
            "title": "Fix issue #35",
            "body": "Closes #35",
            "base": {"ref": "main"},
            "head": {"ref": "agent/issue-35-closure", "sha": "headsha1"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        human_pr = {
            "number": 32,
            "title": "Fix issue #35",
            "body": "Closes #35",
            "base": {"ref": "main"},
            "head": {"ref": "agent/issue-35-closure", "sha": "headsha2"},
            "user": {"login": "liuchangchxy", "type": "User"},
        }

        # 1. Exactly one valid bot PR -> adopted
        status, adopted = dispatcher.adopt_existing_pr("liuchangchxy/easy-exam", 35, pulls_list=[valid_bot_pr])
        self.assertEqual(status, "adopted")
        self.assertEqual(adopted["number"], 31)

        # 2. Candidate PR with invalid human author -> rejected
        status, adopted = dispatcher.adopt_existing_pr("liuchangchxy/easy-exam", 35, pulls_list=[human_pr])
        self.assertEqual(status, "invalid_author")
        self.assertIsNone(adopted)

        # 3. Multiple bot candidate PRs -> needs-human
        second_bot_pr = dict(valid_bot_pr, number=33)
        status, adopted = dispatcher.adopt_existing_pr("liuchangchxy/easy-exam", 35, pulls_list=[valid_bot_pr, second_bot_pr])
        self.assertEqual(status, "needs_human_multiple_candidates")
        self.assertIsNone(adopted)

        # 4. No matching PR -> none_found
        status, adopted = dispatcher.adopt_existing_pr("liuchangchxy/easy-exam", 35, pulls_list=[])
        self.assertEqual(status, "none_found")
        self.assertIsNone(adopted)

    def test_watchdog_timeouts(self):
        # 1. Launch intent stuck for 150s (> 120s deadline)
        old_time = "2026-10-07T00:00:00Z"
        timed_out, reason, target = dispatcher.evaluate_watchdog_timeout(
            {"phase": "LAUNCH_INTENT", "updated_at": old_time},
            now_ts=datetime.fromisoformat("2026-10-07T00:02:31+00:00").timestamp(),
        )
        self.assertTrue(timed_out)
        self.assertEqual(reason, "launch_confirmation_timeout")
        self.assertEqual(target, "infra-blocked")

        # 2. Implementer heartbeat timed out (> 1800s deadline)
        timed_out, reason, target = dispatcher.evaluate_watchdog_timeout(
            {"phase": "LAUNCH_CONFIRMED", "updated_at": old_time},
            now_ts=datetime.fromisoformat("2026-10-07T00:35:00+00:00").timestamp(),
        )
        self.assertTrue(timed_out)
        self.assertEqual(reason, "implementer_heartbeat_timeout")
        self.assertEqual(target, "infra-blocked")

        # 3. Reviewer completion timed out (> 1800s deadline)
        timed_out, reason, target = dispatcher.evaluate_watchdog_timeout(
            {"phase": "WAITING_REVIEW", "updated_at": old_time},
            now_ts=datetime.fromisoformat("2026-10-07T00:35:00+00:00").timestamp(),
        )
        self.assertTrue(timed_out)
        self.assertEqual(reason, "reviewer_completion_timeout")
        self.assertEqual(target, "needs-human")

        # 4. Recent attempt within deadline -> no timeout
        timed_out, _, _ = dispatcher.evaluate_watchdog_timeout(
            {"phase": "LAUNCH_INTENT", "updated_at": old_time},
            now_ts=datetime.fromisoformat("2026-10-07T00:00:30+00:00").timestamp(),
        )
        self.assertFalse(timed_out)

    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_restart_reconciliation_orphan_working_issue(self, mock_fail_closed):
        # Orphan issue with agent-working but no lease and no PR
        with patch.object(dispatcher, "get_open_issues", return_value=[{"number": 99, "labels": [{"name": "agent-working"}]}]):
            with patch.object(dispatcher, "adopt_existing_pr", return_value=("none_found", None)):
                reconciled = dispatcher.reconcile_closure_v1("liuchangchxy/easy-exam", self.ledger)
                self.assertFalse(reconciled)
                mock_fail_closed.assert_called_with("liuchangchxy/easy-exam", 99, "orphan_agent_working_detected")

    def test_crash_before_and_after_launch_confirmation(self):
        # Crash before launch confirmation (phase LAUNCH_INTENT)
        self.ledger.record_claim_intent("liuchangchxy/easy-exam", 35, "w1", "tok", "att-crash", "initial_dispatch", "trig")
        self.ledger.record_launch_intent("att-crash")
        attempt = self.ledger.get_attempt("att-crash")
        self.assertEqual(attempt["phase"], "LAUNCH_INTENT")
        self.assertEqual(attempt["launch_confirmed"], 0)

        # Watchdog marks crash before launch as timed out
        timed_out, reason, target = dispatcher.evaluate_watchdog_timeout(attempt, now_ts=time.time() + 200)
        self.assertTrue(timed_out)
        self.assertEqual(target, "infra-blocked")

        # After launch confirmation (phase LAUNCH_CONFIRMED)
        self.ledger.record_launch_confirmed("att-crash", "conv-uuid-1234")
        attempt_after = self.ledger.get_attempt("att-crash")
        self.assertEqual(attempt_after["phase"], "LAUNCH_CONFIRMED")
        self.assertEqual(attempt_after["launch_confirmed"], 1)
        self.assertEqual(attempt_after["conversation_id"], "conv-uuid-1234")


class ClosureV1ProductionPathIntegrationTests(unittest.TestCase):
    """
    Integration tests verifying Closure v1 engines wired into actual production paths:
    - poll_cycle() executes ExecutionLedger claim/lease/lifecycle.
    - Two-worker lease race prevents duplicate dispatch in poll_cycle().
    - poll_cycle() routes changes-requested to dispatch_automated_repair().
    - Repair budget (max 3, no #4) enforced in production poll_cycle().
    - Exact-SHA fencing enforced in production poll_cycle().
    - Deduplication key enforced in production poll_cycle().
    - Watchdog evaluation executed via poll_cycle() and reconcile_closure_v1().
    """

    def setUp(self):
        self.ledger = dispatcher.ExecutionLedger(":memory:")
        dispatcher.set_ledger(self.ledger)
        dispatcher.CLAIM_BACKOFF_MAP.clear()

    def tearDown(self):
        if hasattr(self, "ledger") and self.ledger:
            self.ledger.close()
        dispatcher.set_ledger(None)
        dispatcher.CLAIM_BACKOFF_MAP.clear()

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "test-uuid-agent-ready"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 42, "title": "Test Task", "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}]}])
    def test_poll_cycle_agent_ready_lifecycle(self, mock_open, mock_details, mock_cas, mock_dispatch):
        dispatcher.poll_cycle()

        # Check lease acquired
        lease = self.ledger.get_active_lease("liuchangchxy/easy-exam", 42)
        self.assertIsNotNone(lease, "Worker must hold active lease after launch")

        # Check attempts in SQLite ledger
        attempts = self.ledger.get_all_attempts_for_issue("liuchangchxy/easy-exam", 42)
        self.assertEqual(len(attempts), 1)
        att = attempts[0]
        self.assertEqual(att["phase"], "LAUNCH_CONFIRMED")
        self.assertEqual(att["launch_confirmed"], 1)
        self.assertEqual(att["conversation_id"], "test-uuid-agent-ready")
        self.assertEqual(att["attempt_kind"], "initial_dispatch")
        self.assertEqual(att["outcome"], "in_progress")

        mock_cas.assert_called_once_with("liuchangchxy/easy-exam", 42, "agent-ready", "agent-working")
        mock_dispatch.assert_called_once()

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "test-uuid-w1"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 42, "title": "Test Task", "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}]}])
    def test_poll_cycle_agent_ready_two_worker_race(self, mock_open, mock_details, mock_cas, mock_dispatch):
        # Worker 1 acquires the lease first
        ok, token, _ = self.ledger.acquire_lease("liuchangchxy/easy-exam", 42, "worker-1")
        self.assertTrue(ok)

        # Worker 2 runs poll_cycle (with a different owner_id in dispatcher)
        with patch("os.getpid", return_value=99999):
            dispatcher.poll_cycle()

        # Worker 2 must have lost the lease race and NOT called CAS or dispatch_agent
        mock_cas.assert_not_called()
        mock_dispatch.assert_not_called()

    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(False, "cas_failed_conflict"))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 42, "title": "Test Task", "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}]}])
    def test_poll_cycle_agent_ready_cas_failure_releases_lease(self, mock_open, mock_details, mock_cas, mock_dispatch):
        dispatcher.poll_cycle()

        mock_dispatch.assert_not_called()
        # Active lease must be released on CAS failure
        lease = self.ledger.get_active_lease("liuchangchxy/easy-exam", 42)
        self.assertIsNone(lease, "Lease must be released if CAS transition fails")

        attempts = self.ledger.get_all_attempts_for_issue("liuchangchxy/easy-exam", 42)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["outcome"], "failed_to_claim")

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "test-uuid-repair-1"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 35, "title": "Task 35", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}])
    def test_poll_cycle_changes_requested_production_repair_path(self, mock_open, mock_details, mock_cas, mock_dispatch):
        head_sha = "1111222233334444555566667777888899990000"
        mock_pr = {
            "number": 36,
            "head": {"sha": head_sha, "ref": "agent/issue-35-closure"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_review = {
            "id": 1001,
            "state": "CHANGES_REQUESTED",
            "commit_id": head_sha,
            "submitted_at": "2026-10-07T05:00:00Z",
        }

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=mock_review):
                dispatcher.poll_cycle()

        mock_cas.assert_called_once_with("liuchangchxy/easy-exam", 35, "changes-requested", "agent-working")
        mock_dispatch.assert_called_once()

        # Check ledger entries
        rep_count = self.ledger.get_repair_count("liuchangchxy/easy-exam", 36)
        self.assertEqual(rep_count, 1)

        attempts = self.ledger.get_all_attempts_for_issue("liuchangchxy/easy-exam", 35)
        self.assertEqual(len(attempts), 1)
        att = attempts[0]
        self.assertEqual(att["attempt_kind"], "reviewer_repair")
        self.assertEqual(att["pr_number"], 36)
        self.assertEqual(att["expected_pr_head_sha"], head_sha)
        self.assertEqual(att["phase"], "PR_BOUND")
        self.assertEqual(att["conversation_id"], "test-uuid-repair-1")

    @patch.object(dispatcher, "fail_closed_to_needs_human", return_value=True)
    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "cas_transition_coordination_state")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 35, "title": "Task 35", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}])
    def test_poll_cycle_changes_requested_budget_exhaustion(self, mock_open, mock_details, mock_cas, mock_dispatch, mock_needs_human):
        head_sha = "1111222233334444555566667777888899990000"
        mock_pr = {
            "number": 36,
            "head": {"sha": head_sha, "ref": "agent/issue-35-closure"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_review = {
            "id": 1004,
            "state": "CHANGES_REQUESTED",
            "commit_id": head_sha,
            "submitted_at": "2026-10-07T05:00:00Z",
        }

        # Seed ledger with 3 completed repairs
        for i in range(1, 4):
            self.ledger.record_claim_intent(
                repo="liuchangchxy/easy-exam",
                issue_number=35,
                owner_id=f"w-{i}",
                lease_token=f"tok-{i}",
                attempt_id=f"att-{i}",
                attempt_kind="reviewer_repair",
                trigger_key=f"trig-{i}",
                pr_number=36,
                repair_ordinal=i,
            )

        self.assertEqual(self.ledger.get_repair_count("liuchangchxy/easy-exam", 36), 3)

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=mock_review):
                dispatcher.poll_cycle()

        # Must fail closed to needs-human and NOT launch 4th repair
        mock_needs_human.assert_called_once()
        mock_cas.assert_not_called()
        mock_dispatch.assert_not_called()

    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "cas_transition_coordination_state")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 35, "title": "Task 35", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}])
    def test_poll_cycle_changes_requested_stale_sha_fencing(self, mock_open, mock_details, mock_cas, mock_dispatch):
        current_sha = "2222222222222222222222222222222222222222"
        reviewed_sha = "1111111111111111111111111111111111111111"
        mock_pr = {
            "number": 36,
            "head": {"sha": current_sha, "ref": "agent/issue-35-closure"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_review = {
            "id": 1005,
            "state": "CHANGES_REQUESTED",
            "commit_id": reviewed_sha,
            "submitted_at": "2026-10-07T05:00:00Z",
        }

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=mock_review):
                dispatcher.poll_cycle()

        # Stale SHA mismatch: no CAS, no dispatch
        mock_cas.assert_not_called()
        mock_dispatch.assert_not_called()
        self.assertEqual(self.ledger.get_repair_count("liuchangchxy/easy-exam", 36), 0)

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "test-uuid-repair-dedupe"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 35, "title": "Task 35", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}])
    def test_poll_cycle_changes_requested_duplicate_review_idempotency(self, mock_open, mock_details, mock_cas, mock_dispatch):
        head_sha = "1111222233334444555566667777888899990000"
        mock_pr = {
            "number": 36,
            "head": {"sha": head_sha, "ref": "agent/issue-35-closure"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_review = {
            "id": 1006,
            "state": "CHANGES_REQUESTED",
            "commit_id": head_sha,
            "submitted_at": "2026-10-07T05:00:00Z",
        }

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=mock_review):
                # Cycle 1: First launch succeeds
                dispatcher.poll_cycle()
                self.assertEqual(mock_dispatch.call_count, 1)

                # Simulate release of issue lease or subsequent cycle with same head SHA
                self.ledger.release_issue_lease("liuchangchxy/easy-exam", 35)

                # Cycle 2: Duplicate review for same head SHA
                dispatcher.poll_cycle()
                # Dispatch count must NOT increase
                self.assertEqual(mock_dispatch.call_count, 1)

    @patch.object(dispatcher, "fail_closed_to_needs_human", return_value=True)
    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    @patch.object(dispatcher, "get_open_issues", return_value=[{"number": 35, "title": "Task 35", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}])
    def test_poll_cycle_changes_requested_missing_pr_fails_closed(self, mock_open, mock_details, mock_dispatch, mock_needs_human):
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("none_found", None)):
            dispatcher.poll_cycle()

        mock_needs_human.assert_called_once_with(
            "liuchangchxy/easy-exam", 35, "no_associated_pr_for_changes_requested"
        )
        mock_dispatch.assert_not_called()

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    @patch.object(dispatcher, "get_open_issues", return_value=[])
    def test_poll_cycle_reconciles_watchdog_timeout(self, mock_open, mock_fail_closed, mock_details):
        # Insert timed-out attempt in ledger (LAUNCH_INTENT created 200s ago)
        old_time = "2026-10-07T00:00:00+00:00"
        self.ledger.acquire_lease("liuchangchxy/easy-exam", 55, "worker-old")
        self.ledger.record_claim_intent(
            repo="liuchangchxy/easy-exam",
            issue_number=55,
            owner_id="worker-old",
            lease_token="tok-old",
            attempt_id="att-timed-out",
            attempt_kind="initial_dispatch",
            trigger_key="trig-old",
        )
        self.ledger.record_launch_intent("att-timed-out")

        # Manually backdate updated_at in DB
        with self.ledger._get_connection() as conn:
            conn.execute("UPDATE execution_ledger SET updated_at = ?, heartbeat_at = ?", (old_time, old_time))
            conn.commit()

        # Run poll_cycle with current time far ahead of deadline
        with patch("time.time", return_value=datetime.fromisoformat("2026-10-07T00:05:00+00:00").timestamp()):
            dispatcher.poll_cycle()

        # Fail closed called for timed-out issue
        mock_fail_closed.assert_called_once()
        att = self.ledger.get_attempt("att-timed-out")
        self.assertEqual(att["outcome"], "timeout_infra_blocked")
        self.assertIsNone(self.ledger.get_active_lease("liuchangchxy/easy-exam", 55))

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_needs_human", return_value=True)
    def test_reconcile_closure_v1_watchdog_timeout_to_needs_human(self, mock_needs_human, mock_details):
        old_time = "2026-10-07T00:00:00+00:00"
        self.ledger.acquire_lease("liuchangchxy/easy-exam", 66, "worker-review")
        self.ledger.record_claim_intent(
            repo="liuchangchxy/easy-exam",
            issue_number=66,
            owner_id="worker-review",
            lease_token="tok-review",
            attempt_id="att-review-timeout",
            attempt_kind="initial_dispatch",
            trigger_key="trig-review",
        )
        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase = 'WAITING_REVIEW', updated_at = ?, heartbeat_at = ?",
                (old_time, old_time),
            )
            conn.commit()

        with patch.object(dispatcher, "get_open_issues", return_value=[]):
            with patch("time.time", return_value=datetime.fromisoformat("2026-10-07T00:35:00+00:00").timestamp()):
                reconciled = dispatcher.reconcile_closure_v1("liuchangchxy/easy-exam", self.ledger)

        self.assertFalse(reconciled)
        mock_needs_human.assert_called_once()
        att = self.ledger.get_attempt("att-review-timeout")
        self.assertEqual(att["outcome"], "timeout_needs_human")
        self.assertIsNone(self.ledger.get_active_lease("liuchangchxy/easy-exam", 66))

    def test_get_latest_changes_requested_review_selection(self):
        reviews = [
            {"id": 1, "state": "COMMENTED", "submitted_at": "2026-10-07T01:00:00Z", "commit_id": "sha1"},
            {"id": 2, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T02:00:00Z", "commit_id": "sha2"},
            {"id": 3, "state": "APPROVED", "submitted_at": "2026-10-07T03:00:00Z", "commit_id": "sha3"},
            {"id": 4, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T04:00:00Z", "commit_id": "sha4"},
        ]
        chosen = dispatcher.get_latest_changes_requested_review("liuchangchxy/easy-exam", 99, reviews_list=reviews)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["id"], 4)
        self.assertEqual(chosen["commit_id"], "sha4")


if __name__ == "__main__":
    unittest.main()
