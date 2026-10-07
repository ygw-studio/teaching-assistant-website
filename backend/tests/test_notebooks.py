import tempfile
import unittest
from pathlib import Path

from app.notebooks import NotebookPool


class NotebookKernelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pool = NotebookPool(Path(self.temp.name), max_kernels=3)

    def tearDown(self):
        self.pool.close_all()
        self.temp.cleanup()

    def test_state_unicode_input_errors_plots_and_account_isolation(self):
        key = ("student-a", "scratch", "notebook-1")
        result = self.pool.execute(key, "x = 10\nprint('你好')")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("你好", str(result["outputs"]))
        self.assertEqual(result["execution_count"], 1)
        result = self.pool.execute(key, "x += 1\nx")
        self.assertEqual(result["outputs"][-1]["data"]["text/plain"], "11")
        self.assertEqual(result["execution_count"], 2)
        other = self.pool.execute(("student-b", "scratch", "notebook-1"), "x")
        self.assertEqual(other["exit_code"], 1)
        self.assertEqual(other["outputs"][-1]["ename"], "NameError")
        result = self.pool.execute(key, "print(int(input('输入：')) + 1)", "41")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("42", str(result["outputs"]))
        result = self.pool.execute(key, "input('输入：')")
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["outputs"][-1]["ename"], "EOFError")
        plot = self.pool.execute(key, "import matplotlib.pyplot as plt\nplt.plot([1, 2, 3]); plt.show()")
        self.assertEqual(plot["exit_code"], 0)
        self.assertTrue(any("image/png" in output.get("data", {}) for output in plot["outputs"]))
        self.pool.restart(key)
        result = self.pool.execute(key, "x")
        self.assertEqual(result["exit_code"], 1)

    def test_timeout_stops_kernel_and_next_execution_starts_clean(self):
        key = ("student-a", "scratch", "timeout")
        result = self.pool.execute(key, "x = 1\nwhile True: pass", timeout=1)
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["kernel_reset"])
        self.assertNotIn(key, self.pool.sessions)
        result = self.pool.execute(key, "x")
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["outputs"][-1]["ename"], "NameError")


if __name__ == "__main__":
    unittest.main()
