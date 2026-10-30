import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shared.authorization import authorized
from shared import memory, team
from fixer_agent.coder import Session
from fixer_agent.workspace import Stack
from tester_agent.web import public_ip

BINDINGS = json.dumps([{"requester":"owner-agent", "repo":"owner/shop", "site":"https://shop.example"}])

class ReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_authorization_before_queueing(self):
        store=memory._Local()
        with patch.dict(os.environ,{"FIXER_REQUESTER_BINDINGS":BINDINGS,"FIXER_ALLOWED_REPOS":"owner/shop"}), patch.object(memory,"_backend",store):
            known={"repo":"owner/shop","site":"https://shop.example"}
            self.assertIn("denied",await team.start_fix("agentready","stranger",known))
            self.assertIn("denied",await team.start_fix("agentready","owner-agent",{**known,"site":"https://attacker.example"}))
            self.assertFalse(store.lists)
            self.assertIn("Handed",await team.start_fix("agentready","owner-agent",known))
            queued=await memory.next_task("fixer")
            self.assertEqual(queued["site"],"https://shop.example")
            self.assertEqual(queued["user"],"owner-agent")
            self.assertIn("disabled",await team.start_merge("agentready","stranger",{**known,"pr_url":"https://github.com/owner/shop/pull/1","fix_state":"done"}))
            self.assertIsNone(await memory.next_task("fixer"))
        with patch.dict(os.environ,{"FIXER_REQUESTER_BINDINGS":"invalid"}):
            self.assertFalse(authorized("owner-agent","owner/shop","https://shop.example"))
        self.assertFalse(authorized("owner-agent","owner/shop","https://shop.example"))

    async def test_warmup_uses_guard(self):
        from agentready_agent.brain import wake_site
        self.assertFalse(await wake_site("http://127.0.0.1/",attempts=1))
        self.assertFalse(await wake_site("http://169.254.169.254/",attempts=1))
        from tester_agent.web import public_client
        with patch("agentready_agent.brain.public_client",wraps=public_client) as factory:
            await wake_site("http://127.0.0.1/",attempts=1)
            self.assertEqual(factory.call_count,1)

    async def test_credential_files_and_executable_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            session=Session(root,Stack("static","Static"),None,None)
            for name in [".netrc",".git-credentials","prod.env","serviceAccountKey.json","secrets.json"]:
                (root/name).write_text("private-fixture")
                result=await session.call("read_file",{"path":name})
                self.assertTrue(result.startswith("Error:"),result)
                self.assertNotIn("private-fixture",result)
            for name in ["package.json","next.config.js","Dockerfile","Dockerfile.prod",".github/workflows/build.yml"]:
                result=await session.call("write_file",{"path":name,"content":"malicious"})
                self.assertTrue(result.startswith("Error:"),result)
                self.assertFalse((root/name).exists())
            (root/"page.txt").write_text("a"*41+"!")
            self.assertEqual(await session.call("search",{"pattern":"(a+)+$"}),"No matches.")
            result=await session.call("write_file",{"path":"index.html","content":"<h1>Shop</h1>"})
            self.assertTrue(result.startswith("Wrote"))

    async def test_ipv6_policy(self):
        for ip in ["64:ff9b::a9fe:a9fe","::7f00:1","fec0::1","2002:7f00:1::","2001::1"]:
            self.assertFalse(public_ip(ip),ip)
        self.assertTrue(public_ip("2606:4700:4700::1111"))
