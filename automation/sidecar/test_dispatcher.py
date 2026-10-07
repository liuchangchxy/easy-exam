import json
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
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.tmp_dir.name) / "dispatch_audit.jsonl"
        self.audit_patcher = patch.object(dispatcher, "DISPATCH_AUDIT_PATH", self.audit_path)
        self.audit_patcher.start()
        self.ledger = dispatcher.ExecutionLedger(":memory:")
        dispatcher.set_ledger(self.ledger)

    def tearDown(self):
        if hasattr(self, "audit_patcher") and self.audit_patcher:
            self.audit_patcher.stop()
        if hasattr(self, "tmp_dir") and self.tmp_dir:
            self.tmp_dir.cleanup()
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

    @patch.object(dispatcher, "get_pull_request_details")
    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "get_issue_details")
    def test_duplicate_failed_checks_deduplication(self, mock_details, mock_dispatch, mock_pr_details):
        mock_details.return_value = {"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]}
        mock_dispatch.return_value = {"launch_confirmed": True, "conversation_id": "test-uuid-1"}

        head_sha = "abcdef1234567890abcdef1234567890abcdef12"
        mock_pr_details.return_value = {
            "number": 15,
            "state": "open",
            "head": {"sha": head_sha, "ref": "agent/branch-1"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
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

    @patch.object(dispatcher, "get_pull_request_details")
    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "transition_succeeded"))
    @patch.object(dispatcher, "get_issue_details")
    def test_duplicate_review_deduplication(self, mock_details, mock_cas, mock_dispatch, mock_pr_details):
        mock_details.return_value = {"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]}
        mock_dispatch.return_value = {"launch_confirmed": True, "conversation_id": "test-uuid-2"}

        rejected_sha = "9999888877776666555544443333222211110000"
        mock_pr_details.return_value = {
            "number": 15,
            "state": "open",
            "head": {"sha": rejected_sha, "ref": "agent/branch-2"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
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
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.tmp_dir.name) / "dispatch_audit.jsonl"
        self.audit_patcher = patch.object(dispatcher, "DISPATCH_AUDIT_PATH", self.audit_path)
        self.audit_patcher.start()
        self.ledger = dispatcher.ExecutionLedger(":memory:")
        dispatcher.set_ledger(self.ledger)
        dispatcher.CLAIM_BACKOFF_MAP.clear()

    def tearDown(self):
        if hasattr(self, "audit_patcher") and self.audit_patcher:
            self.audit_patcher.stop()
        if hasattr(self, "tmp_dir") and self.tmp_dir:
            self.tmp_dir.cleanup()
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
            "state": "open",
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
            with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr):
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
        self.assertEqual(att["phase"], "LAUNCH_CONFIRMED")
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
            "state": "open",
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
            with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr):
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

        # Manually backdate updated_at and phase_entered_at in DB
        with self.ledger._get_connection() as conn:
            conn.execute("UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?", (old_time, old_time, old_time))
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
                "UPDATE execution_ledger SET phase = 'WAITING_REVIEW', phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (old_time, old_time, old_time),
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


class ClosureV1ProductionReachabilityTests(unittest.TestCase):
    """
    Enforces the Production Reachability Rule:
    'Any production lifecycle state must be reachable through a production entrypoint.
     Directly seeding internal state in a test is not sufficient acceptance evidence.'

    Each production lifecycle state (LAUNCH_CONFIRMED, PR_BOUND, WAITING_CI, WAITING_REVIEW,
    WAITING_MERGE, terminal outcomes, automated repair dispatch) is reached through real
    production entrypoints (poll_cycle() or reconcile_closure_v1()).
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.tmp_dir.name) / "dispatch_audit.jsonl"
        self.audit_patcher = patch.object(dispatcher, "DISPATCH_AUDIT_PATH", self.audit_path)
        self.audit_patcher.start()
        self.ledger = dispatcher.ExecutionLedger(":memory:")
        dispatcher.set_ledger(self.ledger)
        dispatcher.CLAIM_BACKOFF_MAP.clear()

        # Hermetic mocks for GitHub read calls
        self.issue_details_patcher = patch.object(
            dispatcher,
            "get_issue_details",
            side_effect=lambda repo, issue_num: {
                "number": issue_num,
                "state": "OPEN",
                "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}],
            },
        )
        self.issue_details_patcher.start()

        self.open_issues_patcher = patch.object(dispatcher, "get_open_issues", return_value=[])
        self.open_issues_patcher.start()

    def tearDown(self):
        if hasattr(self, "open_issues_patcher") and self.open_issues_patcher:
            self.open_issues_patcher.stop()
        if hasattr(self, "issue_details_patcher") and self.issue_details_patcher:
            self.issue_details_patcher.stop()
        if hasattr(self, "audit_patcher") and self.audit_patcher:
            self.audit_patcher.stop()
        if hasattr(self, "tmp_dir") and self.tmp_dir:
            self.tmp_dir.cleanup()
        if hasattr(self, "ledger") and self.ledger:
            self.ledger.close()
        dispatcher.set_ledger(None)
        dispatcher.CLAIM_BACKOFF_MAP.clear()

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "conv-zero-touch-100"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    @patch.object(dispatcher, "execute_coordination_write", return_value=True)
    def test_production_reachability_full_lifecycle_agent_ready_to_merged(
        self, mock_write, mock_cas, mock_dispatch
    ):
        """
        Step through complete production lifecycle through real entrypoints:
        agent-ready (poll_cycle)
        -> LAUNCH_CONFIRMED
        -> PR_BOUND (reconcile_closure_v1)
        -> WAITING_CI (reconcile_closure_v1)
        -> WAITING_REVIEW (reconcile_closure_v1)
        -> WAITING_MERGE (reconcile_closure_v1)
        -> terminal merged_success (reconcile_closure_v1)
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 100
        pr_number = 101
        head_sha = "aabbccddeeff00112233445566778899aabbccdd"
        branch = "agent/issue-100-test-lifecycle"

        # 1. Reach LAUNCH_CONFIRMED via poll_cycle() on agent-ready
        issue_details = {
            "number": issue_number,
            "title": "Full Lifecycle Task",
            "state": "OPEN",
            "labels": [{"name": "frozen-spec"}, {"name": "agent-ready"}],
        }
        with patch.object(dispatcher, "get_open_issues", return_value=[issue_details]):
            with patch.object(dispatcher, "get_issue_details", return_value=issue_details):
                dispatcher.poll_cycle()

        mock_dispatch.assert_called_once()
        active_lease = self.ledger.get_active_lease(repo, issue_number)
        self.assertIsNotNone(active_lease, "Active lease must be held")
        attempts = self.ledger.get_all_attempts_for_issue(repo, issue_number)
        self.assertEqual(len(attempts), 1)
        attempt_id = attempts[0]["attempt_id"]
        att = self.ledger.get_attempt(attempt_id)
        self.assertEqual(att["phase"], "LAUNCH_CONFIRMED")
        self.assertEqual(att["launch_confirmed"], 1)

        # 2. Reach PR_BOUND via reconcile_closure_v1() when PR is discovered
        mock_pr = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": head_sha, "ref": branch},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt(attempt_id)
        self.assertEqual(att["phase"], "PR_BOUND")
        self.assertEqual(att["pr_number"], pr_number)
        self.assertEqual(att["branch"], branch)
        self.assertEqual(att["resulting_head_sha"], head_sha)

        # 3. Reach WAITING_CI via reconcile_closure_v1() when CI checks are pending
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value={"status": "pending", "failed_check": None}):
                dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt(attempt_id)
        self.assertEqual(att["phase"], "WAITING_CI")

        # 4. Reach WAITING_REVIEW via reconcile_closure_v1() when all 5 checks succeed
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value={"status": "success", "failed_check": None}):
                dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt(attempt_id)
        self.assertEqual(att["phase"], "WAITING_REVIEW")

        # 5. Reach WAITING_MERGE via reconcile_closure_v1() when review is APPROVED
        mock_approved_review = {
            "id": 5001,
            "state": "APPROVED",
            "commit_id": head_sha,
            "submitted_at": "2026-10-07T06:00:00Z",
        }
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=None):
                with patch.object(dispatcher, "get_latest_approved_review", return_value=mock_approved_review):
                    dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt(attempt_id)
        self.assertEqual(att["phase"], "WAITING_MERGE")

        # 6. Reach terminal merged_success via reconcile_closure_v1() when PR is merged
        mock_merged_pr = {
            "number": pr_number,
            "state": "closed",
            "merged": True,
            "merged_at": "2026-10-07T06:05:00Z",
            "head": {"sha": head_sha, "ref": branch},
        }
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_merged_pr)):
            dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt(attempt_id)
        self.assertEqual(att["outcome"], "merged_success")
        self.assertEqual(att["resulting_head_sha"], head_sha)
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number), "Lease must be released on terminal merge")

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "conv-repair-ci-1"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    def test_production_reachability_ci_failure_automated_repair(self, mock_cas, mock_dispatch):
        """
        Verify that a code failure in CI reached via reconcile_closure_v1()
        automatically dispatches CI automated repair #1, preserving unified budget.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 101
        pr_number = 202
        failed_sha = "1111222233334444555566667777888899990000"
        branch = "agent/issue-101-ci-fail"

        # Set up active attempt in WAITING_CI via normal ledger methods
        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-ci")
        self.ledger.record_claim_intent(
            repo=repo, issue_number=issue_number, owner_id="worker-ci", lease_token=token,
            attempt_id="att-ci-initial", attempt_kind="initial_dispatch", trigger_key="trig-ci",
            pr_number=pr_number, branch=branch, expected_pr_head_sha=failed_sha
        )
        self.ledger.record_claimed("att-ci-initial")
        self.ledger.record_launch_confirmed("att-ci-initial", "conv-ci-0")
        self.ledger.record_pr_bound("att-ci-initial", pr_number, branch, failed_sha)
        self.ledger.record_phase("att-ci-initial", "WAITING_CI", failed_sha)

        mock_pr = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": failed_sha, "ref": branch},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        failed_check = {
            "name": "Backend & Packaging Tests",
            "state": "FAILURE",
            "bucket": "fail",
            "conclusion": "failure",
            "description": "test failure in test_cases.py",
        }

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr):
                with patch.object(dispatcher, "get_pr_checks_status", return_value={"status": "failure", "failed_check": failed_check}):
                    dispatcher.reconcile_closure_v1(repo, self.ledger)

        # Prior attempt marked repaired_ci_failure
        prior_att = self.ledger.get_attempt("att-ci-initial")
        self.assertEqual(prior_att["outcome"], "repaired_ci_failure")

        # New repair attempt dispatched
        mock_dispatch.assert_called_once()
        rep_count = self.ledger.get_repair_count(repo, pr_number)
        self.assertEqual(rep_count, 1)

        attempts = self.ledger.get_all_attempts_for_issue(repo, issue_number)
        self.assertEqual(len(attempts), 2)
        repair_att = attempts[1]
        self.assertEqual(repair_att["attempt_kind"], "ci_repair")
        self.assertEqual(repair_att["repair_ordinal"], 1)
        self.assertEqual(repair_att["repair_cause_type"], "ci_failure")

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "conv-repair-cr-1"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    def test_production_reachability_reviewer_changes_requested_repair(self, mock_cas, mock_dispatch):
        """
        Verify that Reviewer REQUEST_CHANGES reached via reconcile_closure_v1()
        automatically dispatches Reviewer automated repair #1, preserving unified budget.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 104
        pr_number = 204
        head_sha = "4444555566667777888899990000111122223333"
        branch = "agent/issue-104-cr"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-cr")
        self.ledger.record_claim_intent(
            repo=repo, issue_number=issue_number, owner_id="worker-cr", lease_token=token,
            attempt_id="att-cr-initial", attempt_kind="initial_dispatch", trigger_key="trig-cr",
            pr_number=pr_number, branch=branch, expected_pr_head_sha=head_sha
        )
        self.ledger.record_claimed("att-cr-initial")
        self.ledger.record_launch_confirmed("att-cr-initial", "conv-cr-0")
        self.ledger.record_phase("att-cr-initial", "WAITING_REVIEW", head_sha)

        mock_pr = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": head_sha, "ref": branch},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_cr = {
            "id": 9001,
            "state": "CHANGES_REQUESTED",
            "commit_id": head_sha,
            "submitted_at": "2026-10-07T07:00:00Z",
            "body": "[easyexam-review:" + head_sha + "] please fix invariant",
        }

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr):
                with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=mock_cr):
                    with patch.object(dispatcher, "get_latest_approved_review", return_value=None):
                        dispatcher.reconcile_closure_v1(repo, self.ledger)

        # Prior attempt marked repaired_reviewer_changes_requested
        prior_att = self.ledger.get_attempt("att-cr-initial")
        self.assertEqual(prior_att["outcome"], "repaired_reviewer_changes_requested")

        # New repair attempt dispatched
        mock_dispatch.assert_called_once()
        rep_count = self.ledger.get_repair_count(repo, pr_number)
        self.assertEqual(rep_count, 1)

        attempts = self.ledger.get_all_attempts_for_issue(repo, issue_number)
        self.assertEqual(len(attempts), 2)
        repair_att = attempts[1]
        self.assertEqual(repair_att["attempt_kind"], "reviewer_repair")
        self.assertEqual(repair_att["repair_ordinal"], 1)
        self.assertEqual(repair_att["repair_cause_type"], "changes_requested")

    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_production_reachability_ci_infra_failure_to_infra_blocked(self, mock_infra):
        """
        Verify that an infrastructure CI failure via reconcile_closure_v1()
        transitions to infra-blocked without consuming repair budget.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 102
        pr_number = 203
        sha = "3333444455556666777788889999000011112222"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-infra")
        self.ledger.record_claim_intent(
            repo=repo, issue_number=issue_number, owner_id="worker-infra", lease_token=token,
            attempt_id="att-infra-fail", attempt_kind="initial_dispatch", trigger_key="trig-infra",
            pr_number=pr_number, branch="agent/issue-102", expected_pr_head_sha=sha
        )
        self.ledger.record_claimed("att-infra-fail")
        self.ledger.record_launch_confirmed("att-infra-fail", "conv-infra-0")
        self.ledger.record_phase("att-infra-fail", "WAITING_CI", sha)

        mock_pr = {"number": pr_number, "state": "open", "head": {"sha": sha, "ref": "agent/issue-102"}}
        infra_check = {
            "name": "Backend & Packaging Tests",
            "state": "ERROR",
            "bucket": "error",
            "description": "runner lost communication with the server system_error",
        }
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value={"status": "failure", "failed_check": infra_check}):
                dispatcher.reconcile_closure_v1(repo, self.ledger)

        mock_infra.assert_called_once()
        att = self.ledger.get_attempt("att-infra-fail")
        self.assertEqual(att["outcome"], "infra_failure_blocked")
        self.assertEqual(self.ledger.get_repair_count(repo, pr_number), 0)
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    @patch.object(dispatcher, "fail_closed_to_needs_human", return_value=True)
    def test_production_reachability_watchdog_timeout_waiting_review(self, mock_needs_human):
        """
        Verify that watchdog timeout during WAITING_REVIEW in reconcile_closure_v1()
        transitions to needs-human.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 105
        old_time = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-watchdog")
        self.ledger.record_claim_intent(
            repo=repo, issue_number=issue_number, owner_id="worker-watchdog", lease_token=token,
            attempt_id="att-review-watchdog", attempt_kind="initial_dispatch", trigger_key="trig-wd",
        )
        self.ledger.record_claimed("att-review-watchdog")
        self.ledger.record_launch_confirmed("att-review-watchdog", "conv-wd")
        self.ledger.record_phase("att-review-watchdog", "WAITING_REVIEW")

        with self.ledger._get_connection() as conn:
            conn.execute("UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?", (old_time, old_time, old_time))
            conn.commit()

        mock_pr = {"number": 205, "state": "open", "head": {"sha": "sha-wd", "ref": "agent/branch"}}
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=None):
                with patch.object(dispatcher, "get_latest_approved_review", return_value=None):
                    with patch("time.time", return_value=datetime.fromisoformat("2026-10-07T00:35:00+00:00").timestamp()):
                        dispatcher.reconcile_closure_v1(repo, self.ledger)

        mock_needs_human.assert_called_once()
        att = self.ledger.get_attempt("att-review-watchdog")
        self.assertEqual(att["outcome"], "timeout_needs_human")
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    def test_production_reachability_cancellation_fencing(self):
        """
        Verify that cancellation fencing (issue closed or tagged needs-human)
        terminates active work and releases lease via reconcile_closure_v1().
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 103

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-cancel")
        self.ledger.record_claim_intent(
            repo=repo, issue_number=issue_number, owner_id="worker-cancel", lease_token=token,
            attempt_id="att-cancel", attempt_kind="initial_dispatch", trigger_key="trig-cancel",
        )
        self.ledger.record_launch_confirmed("att-cancel", "conv-cancel-0")

        # GitHub issue now has needs-human label
        cancelled_issue = {
            "number": issue_number,
            "state": "OPEN",
            "labels": [{"name": "frozen-spec"}, {"name": "needs-human"}],
        }
        with patch.object(dispatcher, "get_issue_details", return_value=cancelled_issue):
            dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt("att-cancel")
        self.assertTrue(att["outcome"].startswith("cancelled_"))
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    def test_hardened_repair_contract_prompts(self):
        """
        Verify repair prompt generation contract hardening:
        - Review/CI finding = minimum known defect, not maximum repair scope
        - 6 mandatory rules present
        - Escalation levels 1, 2, 3
        - MAX_AUTOMATED_REPAIRS = 3
        """
        p1 = dispatcher.build_repair_contract_section(1, "changes_requested")
        self.assertIn("minimum known defect, not maximum repair scope", p1)
        self.assertIn("Repair #1 升级强度要求", p1)
        self.assertIn("深入排查根本原因（Root Cause）", p1)
        self.assertIn("MAX_AUTOMATED_REPAIRS = 3", p1)
        for i in range(1, 7):
            self.assertIn(f"{i}. ", p1)

        p2 = dispatcher.build_repair_contract_section(2, "changes_requested")
        self.assertIn("Repair #2 升级强度要求", p2)
        self.assertIn("受影响子系统（Affected subsystem）进行穷尽式全路径审计", p2)

        p3 = dispatcher.build_repair_contract_section(3, "ci_failure")
        self.assertIn("Repair #3 升级强度要求", p3)
        self.assertIn("最后一次自动化修复机会", p3)
        self.assertIn("CI failure finding = minimum known defect", p3)


class ClosureV1WatchdogContinuousPollingAndHeadFencingTests(unittest.TestCase):
    """
    Deterministic production-path tests for:
    1. Preserving stable phase-entry/progress deadlines across continuous polling cycles.
    2. Proving that repeatedly reconciling a stalled attempt while polling continues reaches fail-closed timeouts.
    3. Live PR head fencing returning to WAITING_CI when head changes after WAITING_REVIEW.
    4. Rejecting stale APPROVED / CHANGES_REQUESTED reviews and accepting only reviews anchored to live PR head.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_ledger.db")
        self.ledger = dispatcher.ExecutionLedger(self.db_path)
        self.orig_ledger = dispatcher.get_ledger()
        dispatcher._GLOBAL_LEDGER = self.ledger
        self.audit_path = os.path.join(self.tmp_dir, "dispatch_audit.jsonl")
        self.orig_audit = dispatcher.DISPATCH_AUDIT_PATH
        dispatcher.DISPATCH_AUDIT_PATH = Path(self.audit_path)
        self.mock_open_issues = patch.object(dispatcher, "get_open_issues", return_value=[])
        self.mock_open_issues.start()

    def tearDown(self):
        self.mock_open_issues.stop()
        self.ledger.close()
        dispatcher._GLOBAL_LEDGER = self.orig_ledger
        dispatcher.DISPATCH_AUDIT_PATH = self.orig_audit
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_continuous_polling_stalled_launch_confirmed_times_out(self, mock_fail_closed, mock_details):
        """
        Prove that a continuously polling loop preserves the launch/implementer deadline
        without resetting it, and eventually triggers implementer_heartbeat_timeout.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 301
        t0 = datetime.fromisoformat("2026-10-07T00:00:00+00:00").timestamp()
        t0_iso = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-poll")
        self.ledger.record_claim_intent(repo, issue_number, "worker-poll", token, "att-lc-poll", "initial_dispatch", "trig-lc")
        self.ledger.record_claimed("att-lc-poll")
        self.ledger.record_launch_confirmed("att-lc-poll", "conv-lc-poll")

        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (t0_iso, t0_iso, t0_iso),
            )
            conn.commit()

        # Simulate 5 polling cycles while stalled (no PR created)
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("none_found", None)):
            for offset in (10, 60, 300, 900, 1500):
                poll_ts = t0 + offset
                with patch("time.time", return_value=poll_ts):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=poll_ts)

                att = self.ledger.get_attempt("att-lc-poll")
                self.assertEqual(att["phase"], "LAUNCH_CONFIRMED")
                self.assertEqual(att["outcome"], "in_progress")
                # Stable phase_entered_at must NOT be reset by no-progress polls
                self.assertEqual(att["phase_entered_at"], t0_iso)
                # Dispatcher ownership lease must be maintained
                self.assertIsNotNone(self.ledger.get_active_lease(repo, issue_number))
                mock_fail_closed.assert_not_called()

            # Now poll past the implementer deadline (> 1800s)
            over_ts = t0 + dispatcher.IMPLEMENTER_DEADLINE_SECONDS + 10
            with patch("time.time", return_value=over_ts):
                dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=over_ts)

        mock_fail_closed.assert_called_once_with(repo, issue_number, "implementer_heartbeat_timeout", "att-lc-poll")
        att = self.ledger.get_attempt("att-lc-poll")
        self.assertEqual(att["outcome"], "timeout_infra_blocked")
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_continuous_polling_stalled_waiting_ci_times_out(self, mock_fail_closed, mock_details):
        """
        Prove that a continuously polling loop on pending CI preserves phase_entered_at
        and triggers ci_terminalization_timeout once deadline is exceeded.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 302
        t0 = datetime.fromisoformat("2026-10-07T00:00:00+00:00").timestamp()
        t0_iso = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-ci")
        self.ledger.record_claim_intent(repo, issue_number, "worker-ci", token, "att-ci-poll", "initial_dispatch", "trig-ci")
        self.ledger.record_claimed("att-ci-poll")
        self.ledger.record_launch_confirmed("att-ci-poll", "conv-ci")
        self.ledger.record_phase("att-ci-poll", "WAITING_CI", resulting_head_sha="sha-ci-poll")

        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (t0_iso, t0_iso, t0_iso),
            )
            conn.commit()

        mock_pr = {"number": 102, "state": "open", "head": {"sha": "sha-ci-poll", "ref": "agent/branch"}}
        pending_checks = {"status": "pending", "failed_check": None, "completed_count": 0, "total_checks": 5, "all_checks": []}

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value=pending_checks):
                for offset in (50, 150, 300, 500):
                    poll_ts = t0 + offset
                    with patch("time.time", return_value=poll_ts):
                        dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=poll_ts)

                    att = self.ledger.get_attempt("att-ci-poll")
                    self.assertEqual(att["phase"], "WAITING_CI")
                    self.assertEqual(att["outcome"], "in_progress")
                    self.assertEqual(att["phase_entered_at"], t0_iso)
                    self.assertIsNotNone(self.ledger.get_active_lease(repo, issue_number))
                    mock_fail_closed.assert_not_called()

                # Timeout after 600s
                over_ts = t0 + dispatcher.CI_TERMINALIZATION_DEADLINE_SECONDS + 10
                with patch("time.time", return_value=over_ts):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=over_ts)

        mock_fail_closed.assert_called_once_with(repo, issue_number, "ci_terminalization_timeout", "att-ci-poll")
        att = self.ledger.get_attempt("att-ci-poll")
        self.assertEqual(att["outcome"], "timeout_infra_blocked")
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_needs_human", return_value=True)
    def test_continuous_polling_stalled_waiting_review_times_out(self, mock_fail_closed, mock_details):
        """
        Prove that a continuously polling loop waiting for reviewer preserves phase_entered_at
        and triggers reviewer_completion_timeout to needs-human once deadline is exceeded.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 303
        t0 = datetime.fromisoformat("2026-10-07T00:00:00+00:00").timestamp()
        t0_iso = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-rev")
        self.ledger.record_claim_intent(repo, issue_number, "worker-rev", token, "att-rev-poll", "initial_dispatch", "trig-rev")
        self.ledger.record_claimed("att-rev-poll")
        self.ledger.record_launch_confirmed("att-rev-poll", "conv-rev")
        self.ledger.record_phase("att-rev-poll", "WAITING_REVIEW", resulting_head_sha="sha-rev-poll")

        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (t0_iso, t0_iso, t0_iso),
            )
            conn.commit()

        mock_pr = {"number": 103, "state": "open", "head": {"sha": "sha-rev-poll", "ref": "agent/branch"}}

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=None):
                with patch.object(dispatcher, "get_latest_approved_review", return_value=None):
                    for offset in (100, 400, 800, 1400):
                        poll_ts = t0 + offset
                        with patch("time.time", return_value=poll_ts):
                            dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=poll_ts)

                        att = self.ledger.get_attempt("att-rev-poll")
                        self.assertEqual(att["phase"], "WAITING_REVIEW")
                        self.assertEqual(att["outcome"], "in_progress")
                        self.assertEqual(att["phase_entered_at"], t0_iso)
                        self.assertIsNotNone(self.ledger.get_active_lease(repo, issue_number))
                        mock_fail_closed.assert_not_called()

                    # Timeout after 1800s
                    over_ts = t0 + dispatcher.REVIEWER_COMPLETION_DEADLINE_SECONDS + 10
                    with patch("time.time", return_value=over_ts):
                        dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=over_ts)

        mock_fail_closed.assert_called_once_with(repo, issue_number, "reviewer_completion_timeout", "att-rev-poll")
        att = self.ledger.get_attempt("att-rev-poll")
        self.assertEqual(att["outcome"], "timeout_needs_human")
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_continuous_polling_stalled_waiting_merge_times_out(self, mock_fail_closed, mock_details):
        """
        Prove that a continuously polling loop waiting for auto-merge preserves phase_entered_at
        and triggers auto_merge_timeout once deadline is exceeded.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 304
        t0 = datetime.fromisoformat("2026-10-07T00:00:00+00:00").timestamp()
        t0_iso = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-merge")
        self.ledger.record_claim_intent(repo, issue_number, "worker-merge", token, "att-merge-poll", "initial_dispatch", "trig-merge")
        self.ledger.record_claimed("att-merge-poll")
        self.ledger.record_launch_confirmed("att-merge-poll", "conv-merge")
        self.ledger.record_phase("att-merge-poll", "WAITING_MERGE", resulting_head_sha="sha-merge-poll")

        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (t0_iso, t0_iso, t0_iso),
            )
            conn.commit()

        mock_pr = {"number": 104, "state": "open", "merged": False, "head": {"sha": "sha-merge-poll", "ref": "agent/branch"}}

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            for offset in (50, 150, 300, 500):
                poll_ts = t0 + offset
                with patch("time.time", return_value=poll_ts):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=poll_ts)

                att = self.ledger.get_attempt("att-merge-poll")
                self.assertEqual(att["phase"], "WAITING_MERGE")
                self.assertEqual(att["outcome"], "in_progress")
                self.assertEqual(att["phase_entered_at"], t0_iso)
                self.assertIsNotNone(self.ledger.get_active_lease(repo, issue_number))
                mock_fail_closed.assert_not_called()

            # Timeout after 600s
            over_ts = t0 + dispatcher.AUTO_MERGE_DEADLINE_SECONDS + 10
            with patch("time.time", return_value=over_ts):
                dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=over_ts)

        mock_fail_closed.assert_called_once_with(repo, issue_number, "auto_merge_timeout", "att-merge-poll")
        att = self.ledger.get_attempt("att-merge-poll")
        self.assertEqual(att["outcome"], "timeout_infra_blocked")
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    def test_waiting_review_live_head_change_returns_to_current_head_ci(self, mock_details):
        """
        Verify that when an attempt is in WAITING_REVIEW on sha-old, but a new commit sha-new
        is pushed to the PR, dispatcher detects the head change, records WAITING_CI for sha-new,
        and re-enters the current-head CI path.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 305

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-head-change")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-head-change", token, "att-head-change", "initial_dispatch", "trig-hc",
            pr_number=105,
        )
        self.ledger.record_claimed("att-head-change")
        self.ledger.record_launch_confirmed("att-head-change", "conv-hc")
        self.ledger.record_phase("att-head-change", "WAITING_REVIEW", resulting_head_sha="sha-initial-1111")

        # Live PR has updated head sha-subsequent-2222
        mock_pr = {"number": 105, "state": "open", "head": {"sha": "sha-subsequent-2222", "ref": "agent/branch"}}
        pending_ci = {"status": "pending", "failed_check": None, "completed_count": 0, "total_checks": 5, "all_checks": []}

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value=pending_ci) as mock_get_checks:
                dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt("att-head-change")
        # Attempt must have transitioned back to WAITING_CI for the new head
        self.assertEqual(att["phase"], "WAITING_CI")
        self.assertEqual(att["resulting_head_sha"], "sha-subsequent-2222")
        mock_get_checks.assert_called_with(repo, 105, head_sha="sha-subsequent-2222", checks_data=None)

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    def test_stale_reviews_fenced_and_anchored_reviews_accepted(self, mock_details):
        """
        Verify that:
        1. A stale CHANGES_REQUESTED review on an older SHA does NOT launch repair for current head.
        2. A stale APPROVED review on an older SHA does NOT advance current head to WAITING_MERGE.
        3. A CHANGES_REQUESTED review anchored to current head triggers automated repair.
        4. An APPROVED review anchored to current head advances to WAITING_MERGE.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 306
        head_sha = "0a220d0beb83fb21ce16c804ce4abdd4b68a2aeb"
        old_sha = "b50524c6b5312b280c156084025c41bf7a353d52"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-fenced")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-fenced", token, "att-fenced-rev", "initial_dispatch", "trig-fenced",
            pr_number=106,
        )
        self.ledger.record_claimed("att-fenced-rev")
        self.ledger.record_launch_confirmed("att-fenced-rev", "conv-fenced")
        self.ledger.record_phase("att-fenced-rev", "WAITING_REVIEW", resulting_head_sha=head_sha)

        mock_pr = {"number": 106, "state": "open", "head": {"sha": head_sha, "ref": "agent/branch"}}

        # 1. Stale CHANGES_REQUESTED on old_sha
        stale_cr = [
            {"id": 1, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T01:00:00Z", "commit_id": old_sha, "body": f"[easyexam-review:{old_sha}] fix needed"}
        ]
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(stale_cr), "", False)):
                with patch.object(dispatcher, "dispatch_automated_repair") as mock_repair:
                    dispatcher.reconcile_closure_v1(repo, self.ledger)
                    mock_repair.assert_not_called()

        att = self.ledger.get_attempt("att-fenced-rev")
        self.assertEqual(att["phase"], "WAITING_REVIEW")

        # 2. Stale APPROVED on old_sha
        stale_app = [
            {"id": 2, "state": "APPROVED", "submitted_at": "2026-10-07T02:00:00Z", "commit_id": old_sha, "body": f"Reviewed head: {old_sha}\nlooks good"}
        ]
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(stale_app), "", False)):
                dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt("att-fenced-rev")
        self.assertEqual(att["phase"], "WAITING_REVIEW")

        # 3. Anchored CHANGES_REQUESTED on head_sha -> launches repair
        anchored_cr = [
            {"id": 1, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T01:00:00Z", "commit_id": old_sha, "body": "old"},
            {"id": 3, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T03:00:00Z", "commit_id": head_sha, "body": f"[easyexam-review:{head_sha}]\nfix this"}
        ]
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(anchored_cr), "", False)):
                with patch.object(dispatcher, "dispatch_automated_repair", return_value=(True, "dispatched", {})) as mock_repair:
                    dispatcher.reconcile_closure_v1(repo, self.ledger)
                    mock_repair.assert_called_once()
                    call_kwargs = mock_repair.call_args[1]
                    self.assertEqual(call_kwargs["current_pr_head_sha"], head_sha)
                    self.assertEqual(call_kwargs["expected_repair_baseline_sha"], head_sha)
                    self.assertEqual(call_kwargs["cause_type"], "changes_requested")

        # 4. Anchored APPROVED on head_sha -> advances to WAITING_MERGE
        ok, tok2, _ = self.ledger.acquire_lease(repo, issue_number, "worker-fenced-app")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-fenced-app", tok2, "att-fenced-app", "initial_dispatch", "trig-fenced-app",
            pr_number=106,
        )
        self.ledger.record_claimed("att-fenced-app")
        self.ledger.record_launch_confirmed("att-fenced-app", "conv-fenced-app")
        self.ledger.record_phase("att-fenced-app", "WAITING_REVIEW", resulting_head_sha=head_sha)

        anchored_app = [
            {"id": 4, "state": "APPROVED", "submitted_at": "2026-10-07T04:00:00Z", "commit_id": head_sha, "body": f"[easyexam-review:{head_sha}]\nAPPROVED!"}
        ]
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(anchored_app), "", False)):
                dispatcher.reconcile_closure_v1(repo, self.ledger)

        att = self.ledger.get_attempt("att-fenced-app")
        self.assertEqual(att["phase"], "WAITING_MERGE")
        self.assertEqual(att["resulting_head_sha"], head_sha)

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_transition_to_waiting_ci_resets_phase_entered_at_and_deadline(self, mock_fail_closed, mock_details):
        """
        Verify that transitioning from PR_BOUND to WAITING_CI updates the in-memory
        attempt's phase_entered_at from the newly persisted value, ensuring the new CI
        deadline begins at the transition rather than inheriting prior elapsed time.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 307
        t0 = datetime.fromisoformat("2026-10-07T00:00:00+00:00").timestamp()
        t0_iso = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-trans-ci")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-trans-ci", token, "att-trans-ci", "initial_dispatch", "trig-trans-ci",
            pr_number=107,
        )
        self.ledger.record_claimed("att-trans-ci")
        self.ledger.record_launch_confirmed("att-trans-ci", "conv-trans-ci")
        self.ledger.record_pr_bound("att-trans-ci", 107, "agent/branch", "sha-initial-head")

        # Set phase_entered_at to t0 in DB and attempt
        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (t0_iso, t0_iso, t0_iso),
            )
            conn.commit()

        mock_pr = {"number": 107, "state": "open", "head": {"sha": "sha-initial-head", "ref": "agent/branch"}}
        pending_checks = {"status": "pending", "failed_check": None, "completed_count": 0, "total_checks": 5, "all_checks": []}

        # Transition happens at t0 + 2000s (> IMPLEMENTER_DEADLINE and > CI_TERMINALIZATION_DEADLINE)
        t_trans = t0 + 2000.0
        t_trans_iso = datetime.fromtimestamp(t_trans, tz=timezone.utc).isoformat()

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value=pending_checks):
                with patch("time.time", return_value=t_trans):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=t_trans)

        att = self.ledger.get_attempt("att-trans-ci")
        self.assertEqual(att["phase"], "WAITING_CI")
        self.assertEqual(att["outcome"], "in_progress")
        # phase_entered_at must be the transition time, NOT the old t0 timestamp
        self.assertEqual(att["phase_entered_at"], t_trans_iso)
        # Watchdog must NOT have timed out upon entering WAITING_CI
        mock_fail_closed.assert_not_called()

        # Polling 500s later (still within 1800s CI deadline) must continue without timing out
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value=pending_checks):
                t_poll = t_trans + 500.0
                with patch("time.time", return_value=t_poll):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=t_poll)

                att = self.ledger.get_attempt("att-trans-ci")
                self.assertEqual(att["phase"], "WAITING_CI")
                self.assertEqual(att["outcome"], "in_progress")
                self.assertEqual(att["phase_entered_at"], t_trans_iso)
                mock_fail_closed.assert_not_called()

                # Polling past CI_TERMINALIZATION_DEADLINE_SECONDS from the transition triggers timeout
                t_over = t_trans + dispatcher.CI_TERMINALIZATION_DEADLINE_SECONDS + 10.0
                with patch("time.time", return_value=t_over):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=t_over)

        mock_fail_closed.assert_called_once_with(repo, issue_number, "ci_terminalization_timeout", "att-trans-ci")
        att = self.ledger.get_attempt("att-trans-ci")
        self.assertEqual(att["outcome"], "timeout_infra_blocked")

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    @patch.object(dispatcher, "fail_closed_to_infra_blocked", return_value=True)
    def test_waiting_review_head_change_resets_phase_entered_at(self, mock_fail_closed, mock_details):
        """
        Verify that when an attempt is in WAITING_REVIEW with an old timestamp and a head
        change occurs, transitioning back to WAITING_CI resets phase_entered_at in memory
        and in the ledger so newly started CI does not fail closed immediately.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 308
        t0 = datetime.fromisoformat("2026-10-07T00:00:00+00:00").timestamp()
        t0_iso = "2026-10-07T00:00:00+00:00"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-rev-hc")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-rev-hc", token, "att-rev-hc", "initial_dispatch", "trig-rev-hc",
            pr_number=108,
        )
        self.ledger.record_claimed("att-rev-hc")
        self.ledger.record_launch_confirmed("att-rev-hc", "conv-rev-hc")
        self.ledger.record_phase("att-rev-hc", "WAITING_REVIEW", resulting_head_sha="0a220d0beb83fb21ce16c804ce4abdd4b68a2aeb")

        with self.ledger._get_connection() as conn:
            conn.execute(
                "UPDATE execution_ledger SET phase_entered_at = ?, updated_at = ?, heartbeat_at = ?",
                (t0_iso, t0_iso, t0_iso),
            )
            conn.commit()

        # Head updated at t0 + 2000s (> 1800s)
        new_head = "6f252ec101d2ee0c2c4bbaa7f5882ce595e4b71b"
        mock_pr = {"number": 108, "state": "open", "head": {"sha": new_head, "ref": "agent/branch"}}
        pending_checks = {"status": "pending", "failed_check": None, "completed_count": 0, "total_checks": 5, "all_checks": []}

        t_trans = t0 + 2000.0
        t_trans_iso = datetime.fromtimestamp(t_trans, tz=timezone.utc).isoformat()

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value=pending_checks):
                with patch("time.time", return_value=t_trans):
                    dispatcher.reconcile_closure_v1(repo, self.ledger, now_ts=t_trans)

        att = self.ledger.get_attempt("att-rev-hc")
        self.assertEqual(att["phase"], "WAITING_CI")
        self.assertEqual(att["resulting_head_sha"], new_head)
        self.assertEqual(att["outcome"], "in_progress")
        self.assertEqual(att["phase_entered_at"], t_trans_iso)
        mock_fail_closed.assert_not_called()

    def test_review_target_commit_sha_exactness_and_rejections(self):
        """
        Verify get_review_target_commit_sha requires exact normalized 40-hex equality:
        - Accepts valid 40-hex native commit_id
        - Accepts valid 40-hex formal marker [easyexam-review:<40-hex>]
        - Accepts valid 40-hex 'Reviewed head: <40-hex>' (with or without backticks)
        - Rejects 7-character abbreviated prefix commit_id
        - Rejects 7-character abbreviated prefix formal marker
        - Rejects 7-character abbreviated prefix Reviewed head
        - Rejects conflicting body-marker and native-commit values
        - Rejects conflicting multiple body markers
        """
        sha40_a = "0a220d0beb83fb21ce16c804ce4abdd4b68a2aeb"
        sha40_b = "6f252ec101d2ee0c2c4bbaa7f5882ce595e4b71b"
        sha7 = "0a220d0"

        # Valid 40-hex native commit_id
        self.assertEqual(dispatcher.get_review_target_commit_sha({"commit_id": sha40_a}), sha40_a)
        # Valid 40-hex uppercase normalizes to lowercase
        self.assertEqual(dispatcher.get_review_target_commit_sha({"commit_id": sha40_a.upper()}), sha40_a)
        # Valid 40-hex formal marker
        self.assertEqual(dispatcher.get_review_target_commit_sha({"body": f"[easyexam-review:{sha40_a}]"}), sha40_a)
        # Valid 40-hex Reviewed head plain and backticked
        self.assertEqual(dispatcher.get_review_target_commit_sha({"body": f"Reviewed head: {sha40_a}"}), sha40_a)
        self.assertEqual(dispatcher.get_review_target_commit_sha({"body": f"Reviewed head: `{sha40_a}`"}), sha40_a)
        # Concordant body and commit_id
        self.assertEqual(
            dispatcher.get_review_target_commit_sha({"commit_id": sha40_a, "body": f"[easyexam-review:{sha40_a}]"}),
            sha40_a,
        )

        # Negative tests: 7-character prefixes strictly rejected (returns None)
        self.assertIsNone(dispatcher.get_review_target_commit_sha({"commit_id": sha7}))
        self.assertIsNone(dispatcher.get_review_target_commit_sha({"body": f"[easyexam-review:{sha7}]"}))
        self.assertIsNone(dispatcher.get_review_target_commit_sha({"body": f"Reviewed head: {sha7}"}))
        self.assertIsNone(dispatcher.get_review_target_commit_sha({"body": f"Reviewed head: `{sha7}`"}))

        # Negative tests: conflicting values strictly rejected (returns None)
        self.assertIsNone(dispatcher.get_review_target_commit_sha({
            "commit_id": sha40_a,
            "body": f"[easyexam-review:{sha40_b}]",
        }))
        self.assertIsNone(dispatcher.get_review_target_commit_sha({
            "body": f"[easyexam-review:{sha40_a}]\nReviewed head: {sha40_b}",
        }))

    def test_is_review_anchored_to_sha_exactness(self):
        """
        Verify is_review_anchored_to_sha strictly requires exact 40-hex equality and rejects prefix-only matches.
        """
        sha40 = "0a220d0beb83fb21ce16c804ce4abdd4b68a2aeb"
        sha7 = "0a220d0"

        # Exact 40-hex match
        review_40 = {"commit_id": sha40, "body": f"[easyexam-review:{sha40}]"}
        self.assertTrue(dispatcher.is_review_anchored_to_sha(review_40, sha40))

        # Rejects 7-char prefix in review against 40-char expected
        review_7 = {"commit_id": sha7}
        self.assertFalse(dispatcher.is_review_anchored_to_sha(review_7, sha40))

        # Rejects 7-char prefix as expected_sha against 40-char review
        self.assertFalse(dispatcher.is_review_anchored_to_sha(review_40, sha7))

        # Rejects conflicting review
        review_conflict = {"commit_id": sha40, "body": "[easyexam-review:6f252ec101d2ee0c2c4bbaa7f5882ce595e4b71b]"}
        self.assertFalse(dispatcher.is_review_anchored_to_sha(review_conflict, sha40))

    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    def test_reconcile_rejects_prefix_and_conflicting_reviews(self, mock_details):
        """
        Verify that reconcile_closure_v1 ignores reviews with 7-char prefix or conflicting
        markers, and does not dispatch automated repair or advance to WAITING_MERGE.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 309
        head_sha = "0a220d0beb83fb21ce16c804ce4abdd4b68a2aeb"
        prefix_sha = "0a220d0"
        other_sha = "6f252ec101d2ee0c2c4bbaa7f5882ce595e4b71b"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-neg-rev")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-neg-rev", token, "att-neg-rev", "initial_dispatch", "trig-neg-rev",
            pr_number=109,
        )
        self.ledger.record_claimed("att-neg-rev")
        self.ledger.record_launch_confirmed("att-neg-rev", "conv-neg-rev")
        self.ledger.record_phase("att-neg-rev", "WAITING_REVIEW", resulting_head_sha=head_sha)

        mock_pr = {"number": 109, "state": "open", "head": {"sha": head_sha, "ref": "agent/branch"}}

        # 1. 7-character prefix CHANGES_REQUESTED review must not launch repair
        prefix_cr = [
            {"id": 1, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T01:00:00Z", "commit_id": prefix_sha, "body": f"[easyexam-review:{prefix_sha}] prefix"}
        ]
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(prefix_cr), "", False)):
                with patch.object(dispatcher, "dispatch_automated_repair") as mock_repair:
                    dispatcher.reconcile_closure_v1(repo, self.ledger)
                    mock_repair.assert_not_called()

        att = self.ledger.get_attempt("att-neg-rev")
        self.assertEqual(att["phase"], "WAITING_REVIEW")

        # 2. Conflicting body-marker and native-commit CHANGES_REQUESTED review must not launch repair
        conflict_cr = [
            {"id": 2, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T02:00:00Z", "commit_id": head_sha, "body": f"[easyexam-review:{other_sha}] conflict"}
        ]
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr)):
            with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(conflict_cr), "", False)):
                with patch.object(dispatcher, "dispatch_automated_repair") as mock_repair:
                    dispatcher.reconcile_closure_v1(repo, self.ledger)
                    mock_repair.assert_not_called()

        att = self.ledger.get_attempt("att-neg-rev")
        self.assertEqual(att["phase"], "WAITING_REVIEW")

    def test_get_pr_checks_status_queries_commit_sha_and_validates_required_jobs(self):
        """
        Verify that get_pr_checks_status binds to its head_sha argument, queries the
        commit's check-runs API directly, and requires all 5 jobs on that SHA to succeed.
        """
        repo = "liuchangchxy/easy-exam"
        pr_number = 100
        target_sha = "1111222233334444555566667777888899990000"

        mock_runs = [
            {"name": name, "status": "completed", "conclusion": "success", "head_sha": target_sha, "id": i}
            for i, name in enumerate(dispatcher.REQUIRED_CHECKS, 1)
        ]
        api_response = {"total_count": 5, "check_runs": mock_runs}

        with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(api_response), "", False)) as mock_cmd:
            res = dispatcher.get_pr_checks_status(repo, pr_number, head_sha=target_sha)

            # Proves it called commit check-runs endpoint rather than 'gh pr checks'
            called_argv = mock_cmd.call_args[0][0]
            self.assertIn("api", called_argv)
            self.assertTrue(any(f"repos/{repo}/commits/{target_sha}/check-runs" in arg for arg in called_argv))

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["completed_count"], 5)
            self.assertIsNone(res["failed_check"])

    def test_get_pr_checks_status_failure_on_exact_commit_sha(self):
        """
        Verify that a code failure among the 5 required checks on target_sha is identified as failure.
        """
        repo = "liuchangchxy/easy-exam"
        pr_number = 100
        target_sha = "1111222233334444555566667777888899990000"

        mock_runs = []
        for i, name in enumerate(dispatcher.REQUIRED_CHECKS, 1):
            if name == "Backend & Packaging Tests":
                mock_runs.append({"name": name, "status": "completed", "conclusion": "failure", "head_sha": target_sha, "id": i})
            else:
                mock_runs.append({"name": name, "status": "completed", "conclusion": "success", "head_sha": target_sha, "id": i})
        api_response = {"total_count": 5, "check_runs": mock_runs}

        with patch.object(dispatcher, "run_cmd", return_value=(0, json.dumps(api_response), "", False)):
            res = dispatcher.get_pr_checks_status(repo, pr_number, head_sha=target_sha)
            self.assertEqual(res["status"], "failure")
            self.assertIsNotNone(res["failed_check"])
            self.assertEqual(res["failed_check"]["name"], "Backend & Packaging Tests")

    def test_get_pr_checks_status_requires_all_five_jobs_to_belong_to_head_sha(self):
        """
        Verify that if any of the five required jobs does not belong to target_sha (e.g. from
        another SHA or missing), get_pr_checks_status returns pending and does not classify
        success or failure.
        """
        repo = "liuchangchxy/easy-exam"
        pr_number = 100
        target_sha = "1111222233334444555566667777888899990000"
        foreign_sha = "9999888877776666555544443333222211110000"

        # Case 1: 4 jobs belong to target_sha, 1 job belongs to foreign_sha and failed
        runs_mixed = []
        for i, name in enumerate(dispatcher.REQUIRED_CHECKS, 1):
            if name == "Backend & Packaging Tests":
                runs_mixed.append({"name": name, "status": "completed", "conclusion": "failure", "head_sha": foreign_sha, "id": i})
            else:
                runs_mixed.append({"name": name, "status": "completed", "conclusion": "success", "head_sha": target_sha, "id": i})

        res1 = dispatcher.get_pr_checks_status(repo, pr_number, head_sha=target_sha, checks_data=runs_mixed)
        # Must NOT classify as failure because the failure is on foreign_sha!
        self.assertEqual(res1["status"], "pending")
        self.assertIsNone(res1["failed_check"])

        # Case 2: Only 4 jobs registered (1 missing)
        runs_partial = [
            {"name": name, "status": "completed", "conclusion": "success", "head_sha": target_sha, "id": i}
            for i, name in enumerate(dispatcher.REQUIRED_CHECKS[:4], 1)
        ]
        res2 = dispatcher.get_pr_checks_status(repo, pr_number, head_sha=target_sha, checks_data=runs_partial)
        self.assertEqual(res2["status"], "pending")

    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    def test_production_path_ci_repair_race_head_change_aborts_repair(self, mock_details, mock_dispatch):
        """
        Production race test for CI repair: change the PR head after the lifecycle snapshot/check
        read but before dispatch mutation boundary.
        Proves:
        - No Implementer launch
        - Clean lease release
        - No repair-key consumption for the new head
        - Aborted-stale attempt recorded
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 310
        pr_number = 110
        old_head_sha = "aaaa111122223333444455556666777788889999"
        new_head_sha = "bbbb111122223333444455556666777788889999"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-ci-race")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-ci-race", token, "att-ci-race", "initial_dispatch", "trig-ci-race",
            pr_number=pr_number, branch="agent/race-ci", expected_pr_head_sha=old_head_sha
        )
        self.ledger.record_claimed("att-ci-race")
        self.ledger.record_launch_confirmed("att-ci-race", "conv-ci-race")
        self.ledger.record_phase("att-ci-race", "WAITING_CI", resulting_head_sha=old_head_sha)

        mock_pr_old = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": old_head_sha, "ref": "agent/race-ci"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_pr_new = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": new_head_sha, "ref": "agent/race-ci"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }

        # Snapshot sees mock_pr_old with a failing check
        failed_check = {"name": "Backend & Packaging Tests", "state": "FAILURE", "bucket": "fail", "conclusion": "failure"}
        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr_old)):
            with patch.object(dispatcher, "get_pr_checks_status", return_value={"status": "failure", "failed_check": failed_check}):
                # At mutation boundary, live PR read sees new_head_sha
                with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr_new):
                    dispatcher.reconcile_closure_v1(repo, self.ledger)

        # 1. No Implementer launch
        mock_dispatch.assert_not_called()

        # 2. Clean lease release
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

        # 3. No repair-key consumption for the new head
        new_key = dispatcher.compute_repair_key(repo, pr_number, new_head_sha)
        self.assertFalse(self.ledger.is_repair_key_processed(new_key))

        # 4. Repair attempt was recorded as aborted_stale
        attempts = self.ledger.get_all_attempts_for_issue(repo, issue_number)
        aborted_attempts = [a for a in attempts if a.get("outcome") == "aborted_stale"]
        self.assertEqual(len(aborted_attempts), 1)

    @patch.object(dispatcher, "cas_transition_coordination_state")
    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    def test_production_path_reviewer_repair_race_head_change_aborts_repair(self, mock_details, mock_dispatch, mock_cas):
        """
        Production race test for Reviewer repair: change the PR head after the review read
        but before dispatch mutation boundary.
        Proves:
        - No Implementer launch
        - No changes-requested -> agent-working CAS transition
        - Clean lease release
        - No repair-key consumption for the new head
        - Aborted-stale attempt recorded
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 311
        pr_number = 111
        old_head_sha = "cccc111122223333444455556666777788889999"
        new_head_sha = "dddd111122223333444455556666777788889999"

        ok, token, _ = self.ledger.acquire_lease(repo, issue_number, "worker-rev-race")
        self.ledger.record_claim_intent(
            repo, issue_number, "worker-rev-race", token, "att-rev-race", "initial_dispatch", "trig-rev-race",
            pr_number=pr_number, branch="agent/race-rev", expected_pr_head_sha=old_head_sha
        )
        self.ledger.record_claimed("att-rev-race")
        self.ledger.record_launch_confirmed("att-rev-race", "conv-rev-race")
        self.ledger.record_phase("att-rev-race", "WAITING_REVIEW", resulting_head_sha=old_head_sha)

        mock_pr_old = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": old_head_sha, "ref": "agent/race-rev"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        mock_pr_new = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": new_head_sha, "ref": "agent/race-rev"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }

        mock_cr = {
            "id": 999,
            "state": "CHANGES_REQUESTED",
            "commit_id": old_head_sha,
            "submitted_at": "2026-10-07T08:00:00Z",
            "body": f"[easyexam-review:{old_head_sha}] please update logic",
        }

        with patch.object(dispatcher, "adopt_existing_pr", return_value=("adopted", mock_pr_old)):
            with patch.object(dispatcher, "get_latest_changes_requested_review", return_value=mock_cr):
                with patch.object(dispatcher, "get_latest_approved_review", return_value=None):
                    with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr_new):
                        dispatcher.reconcile_closure_v1(repo, self.ledger)

        # 1. No Implementer launch
        mock_dispatch.assert_not_called()

        # 2. No changes-requested -> agent-working transition
        mock_cas.assert_not_called()

        # 3. Clean lease release
        self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

        # 4. No repair-key consumption for the new head
        new_key = dispatcher.compute_repair_key(repo, pr_number, new_head_sha)
        self.assertFalse(self.ledger.is_repair_key_processed(new_key))

        # 5. Stale repair attempt recorded as aborted_stale
        attempts = self.ledger.get_all_attempts_for_issue(repo, issue_number)
        aborted_attempts = [a for a in attempts if a.get("outcome") == "aborted_stale"]
        self.assertEqual(len(aborted_attempts), 1)

    @patch.object(dispatcher, "dispatch_agent")
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "agent-working"}]})
    def test_dispatch_automated_repair_aborts_if_live_pr_closed_or_not_canonical(self, mock_details, mock_dispatch):
        """
        Verify that dispatch_automated_repair aborts if live PR is closed or has non-canonical author.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 312
        pr_number = 112
        head_sha = "eeee111122223333444455556666777788889999"

        # 1. Closed PR
        closed_pr = {
            "number": pr_number,
            "state": "closed",
            "head": {"sha": head_sha},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        ci_fail = {"name": "Backend & Packaging Tests", "conclusion": "failure"}
        with patch.object(dispatcher, "get_pull_request_details", return_value=closed_pr):
            ok1, res1, _ = dispatcher.dispatch_automated_repair(
                repo=repo, issue_number=issue_number, pr_number=pr_number,
                current_pr_head_sha=head_sha, expected_repair_baseline_sha=head_sha,
                repair_kind="ci_repair", cause_type="ci_failure", cause_id="run-closed",
                failure_detail=ci_fail,
                ledger=self.ledger,
            )
            self.assertFalse(ok1)
            self.assertEqual(res1, "aborted_stale")
            self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))

        # 2. Non-canonical author
        human_pr = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": head_sha},
            "user": {"login": "some-human-user", "type": "User"},
        }
        with patch.object(dispatcher, "get_pull_request_details", return_value=human_pr):
            ok2, res2, _ = dispatcher.dispatch_automated_repair(
                repo=repo, issue_number=issue_number, pr_number=pr_number,
                current_pr_head_sha=head_sha, expected_repair_baseline_sha=head_sha,
                repair_kind="ci_repair", cause_type="ci_failure", cause_id="run-human",
                failure_detail=ci_fail,
                ledger=self.ledger,
            )
            self.assertFalse(ok2)
            self.assertEqual(res2, "aborted_stale")
            self.assertIsNone(self.ledger.get_active_lease(repo, issue_number))
        mock_dispatch.assert_not_called()

    @patch.object(dispatcher, "dispatch_agent", return_value={"launch_confirmed": True, "conversation_id": "conv-repair-lifecycle-1"})
    @patch.object(dispatcher, "cas_transition_coordination_state", return_value=(True, "cas_ok"))
    @patch.object(dispatcher, "get_issue_details", return_value={"state": "OPEN", "labels": [{"name": "frozen-spec"}, {"name": "changes-requested"}]})
    def test_repair_launch_keeps_launch_confirmed_until_new_push_and_advances_to_waiting_ci(self, mock_details, mock_cas, mock_dispatch):
        """
        Integration test verifying:
        1. Both CI and Reviewer repair launches keep attempt in LAUNCH_CONFIRMED with expected_pr_head_sha.
        2. advance_active_lifecycle reconciles:
           - Before push (current_sha == expected_head): remains waiting_for_repair_push.
           - After push (current_sha != expected_head): records PR_BOUND and transitions to WAITING_CI.
        3. Proves old head cannot re-enter review/duplicate loops.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 35
        pr_number = 36
        old_failed_sha = "1111222233334444555566667777888899990000"
        new_repair_sha = "2222333344445555666677778888999900001111"

        # 1. Launch repair
        mock_pr_old = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": old_failed_sha, "ref": "agent/branch-repair"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        with patch.object(dispatcher, "get_pull_request_details", return_value=mock_pr_old):
            ok, reason, meta = dispatcher.dispatch_automated_repair(
                repo=repo,
                issue_number=issue_number,
                pr_number=pr_number,
                current_pr_head_sha=old_failed_sha,
                expected_repair_baseline_sha=old_failed_sha,
                repair_kind="reviewer_repair",
                cause_type="changes_requested",
                cause_id="review-cr-1",
                failure_detail={"id": 123},
                ledger=self.ledger,
                branch="agent/branch-repair",
            )
            self.assertTrue(ok)
            self.assertEqual(reason, "repair_launched")

        att_id = meta["attempt_id"]
        attempt = self.ledger.get_attempt(att_id)
        # Attempt MUST be in LAUNCH_CONFIRMED, NOT PR_BOUND
        self.assertEqual(attempt["phase"], "LAUNCH_CONFIRMED")
        self.assertEqual(attempt["expected_pr_head_sha"], old_failed_sha)
        self.assertEqual(attempt["conversation_id"], "conv-repair-lifecycle-1")

        # 2. Reconcile before new push (current_sha == old_failed_sha)
        adv_ok1, adv_reason1 = dispatcher.advance_active_lifecycle(
            repo, attempt, ledger=self.ledger, pr_details=mock_pr_old
        )
        self.assertTrue(adv_ok1)
        self.assertEqual(adv_reason1, "waiting_for_repair_push")
        attempt_after1 = self.ledger.get_attempt(att_id)
        self.assertEqual(attempt_after1["phase"], "LAUNCH_CONFIRMED")

        # 3. Reconcile after new push (current_sha == new_repair_sha)
        mock_pr_new = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": new_repair_sha, "ref": "agent/branch-repair"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        adv_ok2, adv_reason2 = dispatcher.advance_active_lifecycle(
            repo, attempt, ledger=self.ledger, pr_details=mock_pr_new
        )
        self.assertTrue(adv_ok2)
        self.assertEqual(adv_reason2, "waiting_ci")
        attempt_after2 = self.ledger.get_attempt(att_id)
        # Proven: transitioned to WAITING_CI with resulting_head_sha = new_repair_sha
        self.assertEqual(attempt_after2["phase"], "WAITING_CI")
        self.assertEqual(attempt_after2["resulting_head_sha"], new_repair_sha)

        # 4. Old head cannot re-enter review/duplicate loops
        old_repair_key = dispatcher.compute_repair_key(repo, pr_number, old_failed_sha)
        self.assertTrue(self.ledger.is_repair_key_processed(old_repair_key))

    def test_duplicate_repair_routes_through_in_flight_attempt_and_renews_lease(self):
        """
        Verify that receiving a duplicate failure or changes_requested event when an in-flight
        repair exists routes through it, checks watchdog, renews lease, and does not strand
        in an unmonitored holding pattern.
        """
        repo = "liuchangchxy/easy-exam"
        issue_number = 35
        pr_number = 36
        head_sha = "3333444455556666777788889999000011112222"

        # Set up an active lease and in-flight attempt in LAUNCH_CONFIRMED
        ok, lease_tok, _ = self.ledger.acquire_lease(repo, issue_number, "test-worker-dup")
        att_id = "att-in-flight-repair"
        repair_key = dispatcher.compute_repair_key(repo, pr_number, head_sha)
        self.ledger.record_claim_intent(
            repo, issue_number, "test-worker-dup", lease_tok, att_id, "ci_repair",
            f"trig:{att_id}", pr_number=pr_number, branch="agent/dup",
            expected_pr_head_sha=head_sha, repair_key=repair_key, repair_ordinal=1
        )
        self.ledger.record_claimed(att_id)
        self.ledger.record_launch_confirmed(att_id, "conv-in-flight-dup")

        mock_pr = {
            "number": pr_number,
            "state": "open",
            "head": {"sha": head_sha, "ref": "agent/dup"},
            "user": {"login": "chang-implementer[bot]", "type": "Bot"},
        }
        ci_fail = {"name": "Backend & Packaging Tests", "conclusion": "failure"}

        # Simulate advance_active_lifecycle receiving CI failure on duplicate repair key
        mock_attempt = {
            "attempt_id": "att-new-eval",
            "issue_number": issue_number,
            "pr_number": pr_number,
            "lease_token": lease_tok,
            "phase": "WAITING_CI",
            "resulting_head_sha": head_sha,
        }
        ci_fail_status = {"status": "failure", "failed_check": ci_fail, "completed_count": 5, "total_checks": 5, "all_checks": [ci_fail]}
        with patch.object(dispatcher, "get_pr_checks_status", return_value=ci_fail_status):
            adv_ok, adv_reason = dispatcher.advance_active_lifecycle(
                repo, mock_attempt, ledger=self.ledger, pr_details=mock_pr, checks_data=[ci_fail]
            )
        self.assertTrue(adv_ok)
        self.assertEqual(adv_reason, "duplicate_ci_repair_ignored")

        # Lease must remain active and renewed
        lease = self.ledger.get_active_lease(repo, issue_number)
        self.assertIsNotNone(lease)
        self.assertEqual(lease["lease_token"], lease_tok)

    def test_implementer_heartbeat_progress_extends_watchdog_deadline_and_stalled_fails_closed(self):
        """
        Verify:
        1. When Implementer conversation shows progress, heartbeat_at is refreshed.
        2. An active attempt with fresh heartbeat survives past IMPLEMENTER_DEADLINE_SECONDS from phase_entered_at.
        3. A stalled attempt without fresh heartbeat fails closed (implementer_heartbeat_timeout) after 1800s.
        """
        start_ts = 1000000.0
        now_ts = start_ts + 2000.0  # 2000s > 1800s (IMPLEMENTER_DEADLINE_SECONDS)

        # 1. Stalled attempt (no heartbeat refreshed, heartbeat_at == phase_entered_at = start_ts)
        start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()
        stalled_attempt = {
            "attempt_id": "att-stalled",
            "phase": "LAUNCH_CONFIRMED",
            "phase_entered_at": start_iso,
            "heartbeat_at": start_iso,
            "created_at": start_iso,
        }
        timed_out1, reason1, target1 = dispatcher.evaluate_watchdog_timeout(stalled_attempt, now_ts=now_ts)
        self.assertTrue(timed_out1)
        self.assertEqual(reason1, "implementer_heartbeat_timeout")
        self.assertEqual(target1, "infra-blocked")

        # 2. Active attempt (heartbeat refreshed 100s ago)
        active_hb_ts = now_ts - 100.0
        active_hb_iso = datetime.fromtimestamp(active_hb_ts, tz=timezone.utc).isoformat()
        active_attempt = {
            "attempt_id": "att-active",
            "phase": "LAUNCH_CONFIRMED",
            "phase_entered_at": start_iso,  # phase_entered_at is 2000s ago, preserving phase deadline
            "heartbeat_at": active_hb_iso,  # recent heartbeat
            "created_at": start_iso,
        }
        timed_out2, reason2, target2 = dispatcher.evaluate_watchdog_timeout(active_attempt, now_ts=now_ts)
        self.assertFalse(timed_out2)
        self.assertIsNone(reason2)

        # 3. ExecutionLedger.update_heartbeat updates heartbeat_at without resetting phase_entered_at
        self.ledger.record_claim_intent(
            "liuchangchxy/easy-exam", 35, "w1", "tok1", "att-hb-test", "ci_repair", "trig-hb"
        )
        self.ledger.record_claimed("att-hb-test")
        self.ledger.record_phase("att-hb-test", "LAUNCH_CONFIRMED", phase_entered_at=start_iso)
        reloaded1 = self.ledger.get_attempt("att-hb-test")
        self.assertEqual(reloaded1["phase_entered_at"], start_iso)

        self.ledger.update_heartbeat("att-hb-test")
        reloaded2 = self.ledger.get_attempt("att-hb-test")
        # phase_entered_at must remain untouched
        self.assertEqual(reloaded2["phase_entered_at"], start_iso)
        # heartbeat_at must be updated to recent time
        self.assertNotEqual(reloaded2["heartbeat_at"], start_iso)


if __name__ == "__main__":
    unittest.main()

