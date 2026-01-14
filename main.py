from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import redirect_stdout
import io
import sys
import traceback
import os

app = FastAPI()

class CodeRequest(BaseModel):
    code: str


def safe_repr(value):
    try:
        return repr(value)
    except Exception:
        return "<unrepresentable>"


@app.post("/run")
def run_code(payload: CodeRequest):
    code = payload.code
    steps = []
    output_buffer = io.StringIO()

    user_globals = {}  # IMPORTANT: shared scope

    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == "<string>":
            steps.append({
                "line_no": frame.f_lineno,
                "locals": {
                    k: safe_repr(v)
                    for k, v in frame.f_locals.items()
                    if k != "__builtins__"   # ✅ FILTER
                }
            })
        return tracer

    try:
        sys.settrace(tracer)
        with redirect_stdout(output_buffer):
            exec(code, user_globals)
    except Exception as e:
        # 🚨 STOP tracing BEFORE traceback formatting
        sys.settrace(None)

        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "steps": steps
        }
    finally:
        sys.settrace(None)

    return {
        "status": "success",
        "output": output_buffer.getvalue().strip(),
        "steps": steps
    }
