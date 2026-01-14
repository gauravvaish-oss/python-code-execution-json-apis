from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
import sys, io, traceback, os
from contextlib import redirect_stdout

load_dotenv()

app = FastAPI()

# ✅ NEW Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class CodeRequest(BaseModel):
    code: str

class ExplainRequest(BaseModel):
    code: str
    step: dict | None = None


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
    user_globals = {}

    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == "<string>":
            steps.append({
                "line_no": frame.f_lineno,
                "locals": {
                    k: safe_repr(v)
                    for k, v in frame.f_locals.items()
                    if k != "__builtins__"
                }
            })
        return tracer

    try:
        # 🔴 Compile first to catch indentation/syntax errors
        compiled = compile(code, "<string>", "exec")

        sys.settrace(tracer)
        with redirect_stdout(output_buffer):
            exec(compiled, user_globals)

    except (SyntaxError, IndentationError) as e:
        sys.settrace(None)

        return {
            "status": "compile_error",
            "error_type": type(e).__name__,
            "message": e.msg,
            "line_no": e.lineno,
            "text": e.text,
            "offset": e.offset,
            "steps": []
        }

    except Exception as e:
        sys.settrace(None)

        return {
            "status": "runtime_error",
            "error_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
            "steps": steps
        }

    finally:
        sys.settrace(None)

    return {
        "status": "success",
        "output": output_buffer.getvalue(),
        "steps": steps
    }



@app.post("/explain")
def explain_code(payload: ExplainRequest):
    prompt = f"""
You are a Python tutor.

Explain the following Python code execution in simple terms.
like how variable assignment works, what each line does, and how the program state changes step by step.
explain it in a manner that a beginner can understand. also make explaination compact not lengthy.

CODE:
{payload.code}

CURRENT STEP:
{payload.step}

Explain clearly for beginners.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return {
            "status": "success",
            "explanation": response.text
        }

    except Exception as e:
        return {
            "status": "error",
            "explanation": str(e)
        }
