from __future__ import annotations

from pathlib import Path
import unittest


class ProjectStatusTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_status_page_links_and_preserves_private_boundaries(self):
        status = (self.root / "docs" / "PROJECT_STATUS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Board 14 is complete only for one local-private", status)
        self.assertIn("cannot be replayed", status)
        self.assertIn("docs/reports/2026-09-01-board-14-11-controlled-success-closeout.md", status)
        self.assertIn("must not", status)

    def test_authoritative_documents_do_not_regress_board_14_state(self):
        documents = {
            "AGENTS.md": (self.root / "AGENTS.md").read_text(encoding="utf-8"),
            "README.md": (self.root / "README.md").read_text(encoding="utf-8"),
            "roadmap": (self.root / "docs" / "ROADMAP.md").read_text(
                encoding="utf-8"
            ),
            "boards": (self.root / "docs" / "DEVELOPMENT_BOARDS.md").read_text(
                encoding="utf-8"
            ),
            "handoff": (self.root / "docs" / "PROJECT_HANDOFF.md").read_text(
                encoding="utf-8"
            ),
            "next": (self.root / "docs" / "START_HERE_NEXT_SESSION.md").read_text(
                encoding="utf-8"
            ),
        }
        self.assertIn("Board 14 is complete", documents["AGENTS.md"])
        self.assertIn("Board 14 is complete", documents["README.md"])
        self.assertIn(
            "Status: complete for one local-private controlled synthetic Manager execution",
            documents["roadmap"],
        )
        self.assertIn(
            "Status: complete for one local-private controlled synthetic Manager execution",
            documents["boards"],
        )
        self.assertIn("Board 14 is complete locally and privately", documents["handoff"])
        self.assertIn("Board 14 is complete only in the", documents["next"])
        self.assertNotIn("Board 14 is in progress", documents["AGENTS.md"])
        self.assertNotIn("has no executor", documents["AGENTS.md"])

    def test_canonical_project_goal_is_linked_and_preserves_user_lifecycle(self):
        goal = (self.root / "docs" / "PROJECT_GOAL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("项目初心", goal)
        self.assertIn("最终用户体验", goal)
        self.assertIn("启动、连接或附着所需 Agent", goal)
        self.assertIn("向用户发送“可以开始”的通知和任务开始请求", goal)
        self.assertIn("只要必需成员未就绪，系统就不能向模型发送项目任务", goal)
        self.assertIn("compact", goal)
        self.assertIn("provider_reported", goal)
        self.assertIn("用户是最终授权者", goal)

        entry_documents = [
            (self.root / "README.md").read_text(encoding="utf-8"),
            (self.root / "AGENTS.md").read_text(encoding="utf-8"),
            (self.root / "docs" / "PROJECT_HANDOFF.md").read_text(
                encoding="utf-8"
            ),
            (self.root / "docs" / "ROADMAP.md").read_text(encoding="utf-8"),
            (self.root / "docs" / "START_HERE_NEXT_SESSION.md").read_text(
                encoding="utf-8"
            ),
        ]
        for document in entry_documents:
            self.assertIn("docs/PROJECT_GOAL.md", document)


if __name__ == "__main__":
    unittest.main()
