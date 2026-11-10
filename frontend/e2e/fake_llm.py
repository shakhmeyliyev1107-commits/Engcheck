"""Testlar uchun soxta OpenAI-mos server (lokal model o'rnida). Tarmoqqa chiqmaydi."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

QUOTE = "Ref. P&ID GP-PID-001 Rev A"


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"data": [{"id": "test-model"}]})

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        system, user = (m["content"] for m in data["messages"][:2])
        if "JSON array" in system:   # hujjat sahifasini tekshirish
            items = ([{"quote": QUOTE, "issue": "Havola qilingan reviziya tekshirilsin",
                       "recommendation": "Joriy reviziya bilan solishtiring", "severity": "minor"},
                      {"quote": "bu matn hujjatda yo'q", "issue": "Uydirma", "recommendation": "-", "severity": "critical"}]
                     if QUOTE in user else [])
            content = json.dumps(items)
        else:                        # topilmaga izoh
            cited = ["K1"] if "[K1]" in user else []
            content = "```json\n" + json.dumps({
                "explanation": "Loyiha bosimi ish bosimidan past bo'lmasligi kerak" + (" [K1]." if cited else "."),
                "citations": cited + ["K9"], "assumptions": ["Qiymatlar almashib yozilgan bo'lishi mumkin"]}) + "\n```"
        self._send({"model": "test-model", "choices": [{"message": {"role": "assistant", "content": content}}]})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
