"""A tiny OpenAI-compatible /chat/completions server so the real HTTP client code path is exercised in tests."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class FakeLLM:
    def __init__(self, replies, models=None):
        """replies: list of dicts: {'tool': name, 'args': {...}} | {'content': str} | {'status': 500} | {'raw': str}"""
        self.replies, self.requests, self.headers, self.models = list(replies), [], [], models or []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.endswith("/models"):
                    payload = json.dumps({"data": [{"id": m} for m in outer.models]}).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                    self.wfile.write(payload)
                else:
                    self.send_response(404); self.end_headers()

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                outer.headers.append(dict(self.headers))
                r = outer.replies.pop(0) if outer.replies else {"content": "ok"}
                if "status" in r:
                    self.send_response(r["status"]); self.end_headers(); self.wfile.write(b"boom"); return
                if "raw" in r:
                    payload = r["raw"].encode()
                else:
                    msg = {"role": "assistant", "content": r.get("content")}
                    if "tool" in r:
                        msg["tool_calls"] = [{"id": "c1", "type": "function",
                                              "function": {"name": r["tool"], "arguments": json.dumps(r.get("args", {}))}}]
                    payload = json.dumps({"choices": [{"message": msg}]}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(payload)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown(); self.server.server_close()
