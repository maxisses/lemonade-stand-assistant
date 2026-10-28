"""Campaign integration tests with fake callbacks; no network or inference."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chart/files/lemonade"))
from campaigns import CampaignConflict, CampaignEngine, CampaignError, FUNCTIONAL_CASES


async def benign_or_block(message, source, run_id):
    assert source == "automation"
    if message in {case["prompt"] for case in FUNCTIONAL_CASES[:2]}:
        return {"outcome": "allowed", "response": "Lemons are sour because of citric acid.", "detectors": [], "latency_seconds": .01}
    return {"outcome": "blocked", "response": "", "detectors": ["policy"], "latency_seconds": .01}


class CampaignTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.engines = []
        self.policy = {"version": "policy-v1", "model": "fake-model", "mode": "protected"}

    def engine(self, evaluate=benign_or_block, generate=None, **kwargs):
        path = kwargs.pop("db_path", str(Path(self.directory.name) / (str(len(self.engines)) + ".sqlite")))
        engine = CampaignEngine(path, evaluate, generate, lambda: self.policy.copy(), **kwargs)
        self.engines.append(engine)
        return engine

    async def asyncTearDown(self):
        for engine in self.engines:
            if not engine._closed:
                await engine.shutdown()

    async def settled(self, engine, run_id, desired=None):
        for _ in range(300):
            run = engine.get(run_id)
            if run["status"] in (desired or {"completed", "stopped", "expired", "interrupted", "failed"}):
                return run
            await asyncio.sleep(.001)
        self.fail("Campaign did not reach the expected state: " + engine.get(run_id)["status"])

    async def test_functional_persists_six_results_and_correct_denominators(self):
        engine = self.engine()
        run = await engine.start("functional", "functional-test")
        run = await self.settled(engine, run["id"])
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["summary"]["completed"], 6)
        self.assertEqual(run["summary"]["evaluated_attacks"], 4)
        self.assertEqual(run["summary"]["benign_controls"], 2)
        self.assertEqual(run["summary"]["request_outcomes"]["blocked"], 4)
        self.assertEqual(run["usage"]["call_reservations"], 6)
        self.assertEqual(run["usage"]["output_token_reservations"], 768)
        self.assertEqual(run["usage"]["judge_calls"], 0)
        self.assertFalse(run["usage"]["usage_complete"])
        self.assertEqual(engine.export(run["id"])["campaign"]["summary"], run["summary"])

    async def test_duplicate_start_is_idempotent_but_changed_settings_conflict(self):
        gate = asyncio.Event()
        calls = []
        async def evaluate(*args):
            calls.append(args)
            await gate.wait()
            return await benign_or_block(*args)
        engine = self.engine(evaluate)
        first, second = await asyncio.gather(engine.start("functional", "same-button-click"), engine.start("functional", "same-button-click"))
        self.assertEqual(first["id"], second["id"])
        with self.assertRaises(CampaignConflict):
            await engine.start("functional", "same-button-click", name="Changed settings")
        with self.assertRaises(CampaignConflict):
            await engine.start("functional", "different-click")
        gate.set()
        await self.settled(engine, first["id"])
        self.assertEqual(len(calls), 6)
        again = await engine.start("functional", "same-button-click")
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(len(calls), 6)

    async def test_atomic_active_limit_between_two_connections(self):
        gate = asyncio.Event()
        async def evaluate(*args):
            await gate.wait()
            return await benign_or_block(*args)
        db_path = str(Path(self.directory.name) / "shared.sqlite")
        first = self.engine(evaluate, db_path=db_path)
        second = self.engine(evaluate, db_path=db_path)
        run = await first.start("functional", "connection-one")
        with self.assertRaises(CampaignConflict):
            await second.start("functional", "connection-two")
        gate.set()
        await self.settled(first, run["id"])

    async def test_pause_finishes_inflight_without_dispatching_next_and_resume_continues(self):
        started, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def evaluate(*args):
            calls.append(args)
            started.set()
            await release.wait()
            return await benign_or_block(*args)
        engine = self.engine(evaluate)
        run = await engine.start("functional", "pause-resume-test")
        await started.wait()
        await engine.pause(run["id"])
        release.set()
        await asyncio.sleep(.01)
        self.assertEqual(len(calls), 1)
        self.assertEqual(engine.get(run["id"])["status"], "paused")
        self.assertEqual(engine.get(run["id"])["summary"]["completed"], 1)
        await engine.resume(run["id"])
        self.assertEqual((await self.settled(engine, run["id"]))["status"], "completed")
        self.assertEqual(len(calls), 6)

    async def test_stop_cancels_inflight_and_never_resends(self):
        started = asyncio.Event()
        calls = []
        async def evaluate(*args):
            calls.append(args)
            started.set()
            await asyncio.Event().wait()
        engine = self.engine(evaluate)
        run = await engine.start("functional", "stop-inflight-test")
        await started.wait()
        await engine.stop(run["id"])
        run = await self.settled(engine, run["id"])
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(len(calls), 1)
        self.assertEqual(run["attempts"][0]["outcome"], "cancelled")
        self.assertEqual(run["summary"]["evaluated_attacks"], 0)
        self.assertTrue(all(a["status"] == "cancelled" for a in run["attempts"]))

    async def test_stop_before_worker_first_runs_releases_active_slot(self):
        engine = self.engine()
        run = await engine.start("functional", "stop-before-dispatch")
        await engine.stop(run["id"])
        run = await self.settled(engine, run["id"])
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["usage"]["call_reservations"], 0)
        next_run = await engine.start("functional", "start-after-stop")
        await self.settled(engine, next_run["id"])

    async def test_recovery_marks_uncertain_work_interrupted_without_network(self):
        gate = asyncio.Event()
        async def evaluate(*args):
            await gate.wait()
            return await benign_or_block(*args)
        db_path = str(Path(self.directory.name) / "recovery.sqlite")
        engine = self.engine(evaluate, db_path=db_path)
        run = await engine.start("functional", "before-restart")
        await asyncio.sleep(.005)
        # Simulate a persisted live run after a dead worker, without reusing a task.
        snapshot = engine.db.execute("SELECT document FROM campaigns WHERE id=?", (run["id"],)).fetchone()[0]
        await engine.shutdown()
        recovered_calls = []
        async def recovered_evaluate(*args):
            recovered_calls.append(args)
            return await benign_or_block(*args)
        recovered = self.engine(recovered_evaluate, db_path=db_path)
        recovered.db.execute("UPDATE campaigns SET document=?,status='running' WHERE id=?", (snapshot, run["id"]))
        self.assertEqual(await recovered.start_background(), 1)
        result = recovered.get(run["id"])
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["attempts"][0]["outcome"], "error")
        self.assertEqual(result["attempts"][0]["verdict"], "not_evaluated")
        await asyncio.sleep(.005)
        self.assertEqual(recovered_calls, [])

    async def test_clock_deadline_stops_dispatch_and_preserves_partial_results(self):
        clock = [1000.0]
        calls = []
        async def evaluate(*args):
            calls.append(args)
            clock[0] += 121
            return await benign_or_block(*args)
        engine = self.engine(evaluate, clock=lambda: clock[0])
        run = await engine.start("functional", "deadline-test")
        run = await self.settled(engine, run["id"])
        self.assertEqual(run["status"], "expired")
        self.assertEqual(len(calls), 1)
        self.assertEqual(run["summary"]["completed"], 1)

    async def test_throttling_pauses_without_retry_and_is_not_guardrail_success(self):
        calls = []
        async def evaluate(*args):
            calls.append(args)
            return {"status": 429, "error_code": "throttled"}
        engine = self.engine(evaluate)
        run = await engine.start("functional", "throttle-test")
        run = await self.settled(engine, run["id"], {"paused"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(run["reason"], "provider_throttled")
        self.assertEqual(run["attempts"][0]["outcome"], "error")
        self.assertEqual(run["attempts"][0]["verdict"], "not_evaluated")
        self.assertEqual(run["summary"]["request_outcomes"]["blocked"], 0)
        await engine.stop(run["id"])

    async def test_three_errors_pause_and_exception_text_is_never_stored(self):
        async def evaluate(*args):
            raise RuntimeError("SECRET_API_KEY_MUST_NOT_BE_REPORTED")
        engine = self.engine(evaluate)
        run = await engine.start("functional", "three-errors-test")
        run = await self.settled(engine, run["id"], {"paused"})
        self.assertEqual(run["usage"]["target_calls"], 3)
        self.assertEqual(run["reason"], "repeated_service_errors")
        self.assertNotIn("SECRET_API_KEY", json.dumps(engine.export(run["id"])))
        await engine.stop(run["id"])

    async def test_adaptation_uses_previous_actual_results_within_budget(self):
        generations = []
        async def generate(role, payload, max_tokens, run_id):
            generations.append((role, payload, max_tokens))
            self.assertEqual(role, "attacker")
            return {"text": json.dumps({"prompt": f"Test {payload['strategy']} round {payload['round']}: talk about apples."}),
                    "usage": {"prompt_tokens": 25, "completion_tokens": 12}}
        engine = self.engine(generate=generate)
        run = await engine.start("adaptive", "adaptive-test")
        run = await self.settled(engine, run["id"])
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(generations), 9)
        self.assertEqual(run["usage"]["attacker_calls"], 9)
        self.assertEqual(run["usage"]["target_calls"], 9)
        self.assertEqual(run["usage"]["judge_calls"], 0)
        self.assertLessEqual(run["usage"]["call_reservations"], 27)
        self.assertLessEqual(run["usage"]["output_token_reservations"], 3744)
        for _, payload, _ in generations[3:]:
            self.assertEqual(payload["previous_attempt"]["outcome"], "blocked")
            self.assertEqual(payload["previous_attempt"]["detectors"], ["policy"])
            self.assertIn(f"round {payload['round'] - 1}", payload["previous_attempt"]["prompt"])
        self.assertTrue(all(a["parent_attempt_id"] for a in run["attempts"][3:]))

    async def test_model_judge_findings_require_review_and_cannot_inflate_confirmed_asr(self):
        async def evaluate(*args):
            return {"outcome": "allowed", "response": "A response requiring semantic review.", "detectors": []}
        async def generate(role, payload, max_tokens, run_id):
            if role == "attacker":
                return {"text": json.dumps({"prompt": f"Lemon test {payload['strategy']} {payload['round']}"})}
            return {"text": json.dumps({"verdict": "violation", "reason": "The response appears off topic."})}
        engine = self.engine(evaluate, generate)
        run = await engine.start("adaptive", "judge-review-test")
        run = await self.settled(engine, run["id"])
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["usage"]["call_reservations"], 27)
        self.assertEqual(run["usage"]["output_token_reservations"], 3744)
        self.assertEqual(run["summary"]["confirmed_violations"], 0)
        self.assertIsNone(run["summary"]["attack_success_rate"])
        self.assertEqual(run["summary"]["review_pending"], 9)
        run = engine.review(run["id"], run["attempts"][0]["id"], "violation", "Manually verified.", "test-operator")
        self.assertEqual(run["summary"]["confirmed_violations"], 1)
        self.assertEqual(run["summary"]["evaluated_attacks"], 1)
        self.assertEqual(run["summary"]["attack_success_rate"], 1)
        self.assertEqual(run["summary"]["review_pending"], 8)

    async def test_exact_marker_violation_is_objective_but_plain_allowed_is_inconclusive(self):
        async def evaluate(message, *args):
            return {"outcome": "allowed", "response": "PURPLE_KITE" if "PURPLE_KITE" in message else "I cannot help with that.", "detectors": []}
        engine = self.engine(evaluate)
        run = await self.settled(engine, (await engine.start("functional", "marker-test"))["id"])
        self.assertEqual(run["summary"]["confirmed_violations"], 1)
        self.assertEqual(run["summary"]["verdicts"]["inconclusive"], 3)
        self.assertEqual(run["attempts"][-1]["evaluation_basis"], "exact_instruction_override_marker")

    async def test_rejected_and_service_errors_never_count_as_defenses(self):
        calls = []
        async def evaluate(message, *args):
            calls.append(message)
            return {"outcome": "rejected", "response": "Too long.", "detectors": []}
        engine = self.engine(evaluate)
        run = await self.settled(engine, (await engine.start("functional", "rejection-test"))["id"])
        self.assertEqual(run["summary"]["request_outcomes"]["rejected"], 6)
        self.assertEqual(run["summary"]["evaluated_attacks"], 0)
        self.assertEqual(run["summary"]["verdicts"]["resisted"], 0)
        with self.assertRaises(CampaignError):
            engine.review(run["id"], run["attempts"][0]["id"], "control_passed")

    async def test_attacker_refusal_and_overlong_generation_do_not_reach_target(self):
        evaluations = []
        async def evaluate(*args):
            evaluations.append(args)
            return await benign_or_block(*args)
        async def generate(*args):
            return {"text": "I cannot generate this prompt."}
        engine = self.engine(evaluate, generate)
        run = await self.settled(engine, (await engine.start("adaptive", "attacker-refusal-test"))["id"], {"paused"})
        self.assertEqual(evaluations, [])
        self.assertEqual(run["usage"]["target_calls"], 0)
        self.assertEqual(run["attempts"][0]["error_code"], "attacker_refusal")
        await engine.stop(run["id"])
        await self.settled(engine, run["id"])
        async def overlong(*args):
            return {"text": "x" * 101}
        engine.generate = overlong
        next_run = await self.settled(engine, (await engine.start("adaptive", "attacker-long-test"))["id"], {"paused"})
        self.assertEqual(next_run["attempts"][0]["error_code"], "invalid_attack_length")
        self.assertEqual(evaluations, [])
        await engine.stop(next_run["id"])

    async def test_retest_keeps_exact_prompts_and_adds_benign_controls(self):
        engine = self.engine()
        original = await self.settled(engine, (await engine.start("functional", "original-for-retest"))["id"])
        chosen = original["attempts"][2]
        self.policy["version"] = "policy-v2"
        retest = await engine.start("retest", "selected-retest", [chosen["id"]], original["id"])
        retest = await self.settled(engine, retest["id"])
        self.assertEqual(retest["attempts"][0]["prompt"], chosen["prompt"])
        self.assertEqual(retest["attempts"][0]["source_attempt_id"], chosen["id"])
        self.assertEqual(retest["summary"]["benign_controls"], 2)
        self.assertEqual(retest["summary"]["planned"], 3)
        self.assertEqual(retest["policy"]["version"], "policy-v2")
        self.assertEqual(retest["comparison"]["previous_policy"]["version"], "policy-v1")
        self.assertTrue(retest["comparison"]["policy_changed"])
        with self.assertRaises(CampaignError):
            await engine.start("retest", "invalid-selection", ["invented-id"], original["id"])

    async def test_policy_change_mid_run_pauses_and_cannot_silently_resume(self):
        async def evaluate(*args):
            self.policy["version"] = "policy-v2"
            return await benign_or_block(*args)
        engine = self.engine(evaluate)
        run = await self.settled(engine, (await engine.start("functional", "policy-change-test"))["id"], {"paused"})
        self.assertEqual(run["reason"], "policy_changed")
        self.assertEqual(run["policy"]["version"], "policy-v1")
        with self.assertRaises(CampaignConflict):
            await engine.resume(run["id"])
        await engine.stop(run["id"])

    async def test_budget_reservation_precedes_dispatch(self):
        started, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def evaluate(*args):
            calls.append(args)
            started.set()
            await release.wait()
            return await benign_or_block(*args)
        engine = self.engine(evaluate)
        run = await engine.start("functional", "budget-test")
        await started.wait()
        self.assertEqual(engine.get(run["id"])["usage"]["call_reservations"], 1)
        engine._mutate(run["id"], lambda r: r["budget"].update(max_calls=1))
        release.set()
        run = await self.settled(engine, run["id"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(run["reason"], "campaign_budget_exhausted")

    async def test_custom_profiles_preserve_controls_and_freeze_idempotent_settings(self):
        engine=self.engine()
        options={"case_ids":["instruction-marker"],"max_seconds":45}
        run=await engine.start("functional","custom-profile-run",options=options,concurrency=2)
        options["case_ids"].append("topic-apples")
        run=await self.settled(engine,run["id"])
        self.assertEqual([a["case_id"] for a in run["attempts"]],["benign-lemons","benign-picnic","instruction-marker"])
        self.assertEqual(run["budget"]["concurrency"],2)
        self.assertEqual(run["budget"]["max_seconds"],45)
        self.assertEqual(run["profile_definition"]["options"]["case_ids"],["benign-lemons","benign-picnic","instruction-marker"])
        with self.assertRaises(CampaignConflict):
            await engine.start("functional","custom-profile-run",options={"case_ids":["instruction-marker"],"max_seconds":45},concurrency=3)
        for invalid in [{"case_ids":["invented"]},{"max_seconds":29},{"max_seconds":181},{"endpoint":"https://other.example"}]:
            with self.assertRaises(CampaignError):engine.validate_profile("functional",invalid)
        for invalid in [{"strategies":[]},{"strategies":["topic","topic"]},{"rounds":4},{"rounds":True}]:
            with self.assertRaises(CampaignError):engine.validate_profile("adaptive",invalid)

    async def test_parallel_functional_pool_honors_limit_and_pause(self):
        release,entered=asyncio.Event(),asyncio.Event()
        active=0;peak=0;calls=[]
        async def evaluate(*args):
            nonlocal active,peak
            calls.append(args)
            active+=1;peak=max(peak,active)
            if len(calls)==2:entered.set()
            try:
                await release.wait()
                await asyncio.sleep(.001)
                return await benign_or_block(*args)
            finally:active-=1
        engine=self.engine(evaluate)
        run=await engine.start("functional","parallel-pause-run",concurrency=2)
        await asyncio.wait_for(entered.wait(),1)
        await engine.pause(run["id"])
        release.set()
        for _ in range(100):
            if engine.get(run["id"])["summary"]["completed"]==2:break
            await asyncio.sleep(.001)
        self.assertEqual(len(calls),2)
        self.assertEqual(active,0)
        await engine.resume(run["id"])
        result=await self.settled(engine,run["id"])
        self.assertEqual(result["summary"]["completed"],6)
        self.assertEqual(peak,2)

    async def test_parallel_stop_joins_children_before_return_and_never_dispatches_more(self):
        entered=asyncio.Event();calls=[];cancelled=[]
        async def evaluate(*args):
            calls.append(args)
            if len(calls)==4:entered.set()
            try:await asyncio.Event().wait()
            finally:cancelled.append(args)
        engine=self.engine(evaluate)
        run=await engine.start("functional","parallel-stop-run",concurrency=4)
        await asyncio.wait_for(entered.wait(),1)
        stopped=await engine.stop(run["id"])
        self.assertEqual(stopped["status"],"stopped")
        self.assertEqual(len(cancelled),4)
        self.assertEqual(len(calls),4)
        self.assertEqual(stopped["summary"]["request_outcomes"]["cancelled"],4)
        self.assertTrue(engine._tasks[run["id"]].done())

    async def test_parallel_adaptive_chains_use_only_their_previous_completed_result(self):
        generated=[];completed=set();active=0;peak=0
        async def generate(role,payload,max_tokens,run_id):
            nonlocal active,peak
            self.assertEqual(role,"attacker")
            category,round_number=payload["strategy"],payload["round"]
            if round_number>1:
                self.assertIn((category,round_number-1),completed)
                self.assertEqual(payload["previous_attempt"]["prompt"],f"{category} round {round_number-1}")
            generated.append((category,round_number))
            active+=1;peak=max(peak,active)
            await asyncio.sleep(.003)
            active-=1
            return {"text":json.dumps({"prompt":f"{category} round {round_number}"})}
        async def evaluate(message,*args):
            category,_,round_number=message.split()
            await asyncio.sleep(.001)
            completed.add((category,int(round_number)))
            return {"outcome":"blocked","response":"","detectors":["policy"]}
        engine=self.engine(evaluate,generate)
        run=await engine.start("adaptive","parallel-adaptive",options={"strategies":["topic","instruction"],"rounds":2,"max_seconds":60},concurrency=3)
        result=await self.settled(engine,run["id"])
        self.assertEqual(result["summary"]["completed"],4)
        self.assertEqual(peak,2)
        self.assertEqual({a["total_rounds"] for a in result["agents"]},{2})
        self.assertEqual(result["budget"]["max_calls"],12)
        self.assertEqual(result["usage"]["attacker_calls"],4)
        self.assertEqual(result["usage"]["target_calls"],4)

    async def test_parallel_deadline_cancels_every_inflight_child(self):
        clock=[100.0];entered=asyncio.Event();cancelled=[];calls=[]
        async def evaluate(*args):
            calls.append(args)
            if len(calls)==3:entered.set()
            try:
                if args[0]==FUNCTIONAL_CASES[0]['prompt']:
                    await asyncio.sleep(.02)
                    clock[0]=131.0
                    return await benign_or_block(*args)
                await asyncio.Event().wait()
            finally:cancelled.append(args)
        engine=self.engine(evaluate,clock=lambda:clock[0])
        run=await engine.start("functional","parallel-deadline",options={"max_seconds":30},concurrency=3)
        await entered.wait()
        result=await self.settled(engine,run["id"])
        self.assertEqual(result["status"],"expired")
        self.assertEqual(len(calls),3)
        self.assertEqual(len(cancelled),3)


if __name__ == "__main__":
    unittest.main()
