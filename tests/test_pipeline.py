"""離線整合測試：在本機架一個假的富邦網站(回傳 1707 的測試頁面，Big5 編碼)，
跑完整的 crawler.build 流程，檢查輸出的 JSON。"""
import http.server
import json
import os
import re
import tempfile
import threading
import unittest


def rj(path):
    with open(path, encoding="utf8") as f:
        return json.load(f)

FX = os.path.join(os.path.dirname(__file__), "fixtures", "1707")
ROUTES = {
    r"zcq/zcqa/zcqa_(\d+)\.djhtm": "isA", r"zcq/zcq_(\d+)\.djhtm": "isQ",
    r"zcp/zcpb/zcpb_(\d+)\.djhtm": "bsA", r"zcp/zcpa/zcpa_(\d+)\.djhtm": "bsQ",
    r"zc3/zc3a_(\d+)\.djhtm": "cfA", r"zc3/zc3_(\d+)\.djhtm": "cfQ",
    r"zcr/zcra/zcra_(\d+)\.djhtm": "frA", r"zcr/zcr_(\d+)\.djhtm": "frQ",
    r"zca/zca_(\d+)\.djhtm": "basic", r"zcc/zcc_(\d+)\.djhtm": "div",
    r"zck/zck_(\d+)\.djhtm": "bm", r"zch/zch_(\d+)\.djhtm": "rev",
}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("/z/zc/", 1)[-1]
        for pat, name in ROUTES.items():
            m = re.fullmatch(pat, path)
            if m:
                if m.group(1) != "1707":      # 其他股票：模擬「查無資料」
                    body = "<html><body>查無資料</body></html>".encode("big5hkscs") + b" " * 300
                else:
                    with open(os.path.join(FX, name + ".html"), encoding="utf8") as f:
                        body = f.read().replace('charset="big5"', 'charset="big5"').encode("big5hkscs", errors="replace")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=big5")
                self.end_headers()
                self.wfile.write(body)
                return
        self.send_response(404)
        self.end_headers()


class TestPipeline(unittest.TestCase):
    def test_build_end_to_end(self):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        os.environ["TWSTOCK_FUBON_BASE"] = f"http://127.0.0.1:{srv.server_port}/z/zc/"
        try:
            import importlib
            from crawler import fubon, build
            importlib.reload(fubon)
            importlib.reload(build)
            with tempfile.TemporaryDirectory() as d:
                state, out = os.path.join(d, "state"), os.path.join(d, "out")
                os.makedirs(state)
                uni = [{"code": "1707", "name": "葡萄王", "listed": "1982-12-20", "market": "上市", "industry": "生技醫療業"},
                       {"code": "9999", "name": "查無股", "listed": "2000-01-01", "market": "上市", "industry": "其他"}]
                with open(os.path.join(state, "universe.json"), "w", encoding="utf8") as f:
                    json.dump(uni, f, ensure_ascii=False)
                cfg = os.path.join(d, "cfg.json")
                with open(cfg, "w") as f:
                    json.dump({"request_delay_sec": 0.0}, f)
                rc = build.main(["--state", state, "--out", out, "--skip-universe", "--config", cfg,
                                 "--refs", os.path.join(d, "none.json")])
                self.assertEqual(rc, 0)
                idx = rj(os.path.join(out, "index.json"))
                self.assertEqual(idx["meta"]["n_stocks"], 1)
                s = idx["stocks"][0]
                self.assertEqual((s["c"], s["s"], s["g"], s["k"]), ("1707", 15, "A-（ROE下滑）", 8))
                self.assertEqual(s["p"], 81.8)
                det = rj(os.path.join(out, "stocks", "1707.json"))
                self.assertTrue(det["links"]["report"].endswith("_1707_AI1.pdf"))
                self.assertEqual(len(det["matrix"]), 8)
                # 查無資料的股票應被標記，而不是當成失敗
                st = rj(os.path.join(state, "facts", "9999.json"))
                self.assertEqual(st["status"], "nodata")
        finally:
            srv.shutdown()
            srv.server_close()
            os.environ.pop("TWSTOCK_FUBON_BASE", None)


if __name__ == "__main__":
    unittest.main()
